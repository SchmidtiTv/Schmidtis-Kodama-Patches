import { useEffect, useRef } from "react";
import { isNativeRuntime, native } from "@/shared/api/tauri.js";
import { toNativePlaybackTrack } from "@/features/player/index.js";
import {
  getTogether,
  useTogetherValue,
  getTune,
  hostSet,
  hostQueue,
  sendReady,
  serverNow,
  expectedPos,
  setDrift,
  setSync,
  inviteLink,
  finishRoomRestore,
} from "./together.js";
import { hostRoomRestorePlan } from "./room-session.js";

/** The webview relays room observations. Native playback owns loading, queue progression,
 * seeking, scheduled starts and rate correction, including while this window is hidden. */
export function useTogetherSync({ currentTrack, queue, setQueue }) {
  const active = useTogetherValue(
    (room) => room.status === "open" || room.status === "reconnecting"
  );
  const isHost = useTogetherValue((room) => room.isHost);
  const roomCode = useTogetherValue((room) => room.room);
  const showDiscord = useTogetherValue((room) => room.showDiscord);
  const restoring = useTogetherValue((room) => room.restoring);
  const readyTrack = useRef(null);
  const host = useRef({ track: null, waiting: false, since: 0 });

  useEffect(() => {
    if (!isNativeRuntime()) return;
    native
      .setPlayerTogether({
        active,
        listener: active && !isHost,
        inviteUrl: active && showDiscord ? inviteLink(roomCode) : null,
      })
      .catch(() => {});
  }, [active, isHost, roomCode, showDiscord]);

  useEffect(
    () => () => {
      if (isNativeRuntime())
        native
          .setPlayerTogether({ active: false, listener: false, inviteUrl: null })
          .catch(() => {});
    },
    []
  );

  useEffect(() => {
    if (!active || !isNativeRuntime()) return;
    let cancelled = false;
    let unlisten = () => {};
    import("@tauri-apps/api/event")
      .then(({ listen }) =>
        listen("audio-loaded", async () => {
          const snapshot = await native.getPlayerSnapshot().catch(() => null);
          if (cancelled) return;
          readyTrack.current = snapshot?.currentTrack?.videoId || null;
          if (readyTrack.current) sendReady(readyTrack.current);
        })
      )
      .then((cleanup) => {
        if (cancelled) cleanup();
        else unlisten = cleanup;
      });
    return () => {
      cancelled = true;
      unlisten();
    };
  }, [active]);

  useEffect(() => {
    if (!active || !isHost) return;
    const room = getTogether();
    if (room.restoring) return;
    const sameTrack = currentTrack?.videoId && room.state?.track?.videoId === currentTrack.videoId;
    host.current = {
      track: currentTrack?.videoId,
      waiting: !sameTrack && !!currentTrack,
      since: Date.now(),
    };
    if (sameTrack) return; // a handover continues the room's current song
    hostSet(currentTrack, false, 0);
    if (currentTrack && isNativeRuntime()) {
      native.playerPause().catch(() => {});
      const tune = getTune();
      native
        .syncPlayerTogether({
          state: {
            track: toNativePlaybackTrack(currentTrack),
            playing: false,
            pos: 0,
            at: Date.now(),
            rate: 1,
          },
          latencyMs: 0,
          seekAboveMs: tune.seekAbove,
          maxRate: tune.maxRate,
        })
        .catch(() => {});
    }
  }, [active, isHost, currentTrack]);

  useEffect(() => {
    if (!active || !isHost) return;
    if (getTogether().restoring) return;
    const index = queue.findIndex((track) => track.videoId === currentTrack?.videoId);
    hostQueue(index >= 0 ? queue.slice(index + 1, index + 21) : []);
  }, [active, isHost, currentTrack, queue]);

  useEffect(() => {
    if (!active || !isHost || !restoring || !isNativeRuntime()) return;
    const room = getTogether();
    const plan = hostRoomRestorePlan(room);
    if (!plan) {
      finishRoomRestore();
      return;
    }
    setQueue(plan.queue);
    const tune = getTune();
    native
      .syncPlayerTogether({
        state: {
          ...plan.state,
          track: toNativePlaybackTrack(plan.state.track),
          at: plan.state.at - room.offset,
        },
        latencyMs: 0,
        seekAboveMs: tune.seekAbove,
        maxRate: tune.maxRate,
      })
      .catch(() => {});
  }, [active, isHost, restoring, setQueue]);

  useEffect(() => {
    if (!active || !isNativeRuntime()) return;
    let cancelled = false;
    let running = false;
    const tick = async () => {
      if (running) return;
      running = true;
      try {
        const snapshot = await native.getPlayerSnapshot();
        if (cancelled) return;
        const room = getTogether();
        const tune = getTune();
        if (room.isHost && room.restoring) {
          const plan = hostRoomRestorePlan(room);
          if (!plan) {
            finishRoomRestore();
            return;
          }
          await native.syncPlayerTogether({
            state: {
              ...plan.state,
              track: toNativePlaybackTrack(plan.state.track),
              at: plan.state.at - room.offset,
            },
            latencyMs: 0,
            seekAboveMs: tune.seekAbove,
            maxRate: tune.maxRate,
          });
          const statusMatches = plan.state.playing
            ? snapshot.status === "playing"
            : snapshot.status === "paused";
          if (snapshot.currentTrack?.videoId === plan.state.track.videoId && statusMatches) {
            host.current = {
              track: plan.state.track.videoId,
              waiting: false,
              since: Date.now(),
            };
            finishRoomRestore();
          }
          return;
        }
        if (!room.isHost) {
          if (!room.state) return;
          if (readyTrack.current === room.state.track?.videoId) sendReady(readyTrack.current);
          await native.syncPlayerTogether({
            state: {
              ...room.state,
              track: toNativePlaybackTrack(room.state.track),
              at: room.state.at - room.offset,
            },
            latencyMs: tune.latency,
            seekAboveMs: tune.seekAbove,
            maxRate: tune.maxRate,
          });
          setDrift(Math.round((snapshot.positionSeconds - expectedPos(room.state)) * 1000));
          setSync({ phase: room.state.playing ? "following" : "paused" });
          return;
        }
        const track = snapshot.currentTrack;
        if (!track || track.videoId !== currentTrack?.videoId) return;
        const pending = host.current;
        if (pending.waiting) {
          if (readyTrack.current !== track.videoId && Date.now() - pending.since < 20000) return;
          const waiting =
            room.config.waitAll &&
            room.members.some((member) => !member.host && member.ready !== track.videoId);
          if (waiting && Date.now() - pending.since < 8000) return;
          const start = serverNow() + 1500;
          hostSet(currentTrack, true, snapshot.positionSeconds, start);
          await native.syncPlayerTogether({
            state: {
              track,
              playing: true,
              pos: snapshot.positionSeconds,
              at: start - room.offset,
              rate: 1,
            },
            latencyMs: 0,
            seekAboveMs: tune.seekAbove,
            maxRate: tune.maxRate,
          });
          host.current = { ...pending, waiting: false, start: start - room.offset };
          return;
        }
        if (Date.now() < (pending.start || 0) + 300) return;
        const playing = snapshot.status === "playing";
        const drift = snapshot.positionSeconds - expectedPos(room.state);
        setDrift(Math.round(drift * 1000));
        if (
          !room.state ||
          room.state.playing !== playing ||
          Math.abs(drift) * 1000 > tune.hostReport
        ) {
          hostSet(currentTrack, playing, snapshot.positionSeconds);
        }
      } catch {
        setSync({ phase: "unavailable" });
      } finally {
        running = false;
      }
    };
    tick();
    const timer = setInterval(tick, 250);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [active, currentTrack]);
}
