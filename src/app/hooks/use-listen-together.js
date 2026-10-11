import { useCallback, useEffect, useRef } from "react";
import { translate } from "@/shared/i18n/i18n.js";
import {
  canAddSongs,
  getTogether,
  isRoomListener,
  join,
  leave,
  onRoomAdd,
  onRoomNotice,
  onRoomRemove,
  parseRoomInput,
  requestAdd,
  setIdentity,
  suggest,
} from "@/features/together/index.js";

/** Coordinates profile identity, room intentions and native-owned player actions. */
export function useListenTogether({ player, profile, addToast, roomIntentRef: suppliedRef }) {
  const ownRef = useRef(null);
  const roomIntentRef = suppliedRef || ownRef;
  useEffect(() => {
    roomIntentRef.current = {
      isListener: isRoomListener,
      isHost: () => {
        const room = getTogether();
        return (room.status === "open" || room.status === "reconnecting") && room.isHost;
      },
      play: suggest,
      enqueue: (track, mode) => (canAddSongs() ? requestAdd(track, mode) : suggest(track)),
    };
  }, [roomIntentRef]);
  const joinRoom = useCallback((input) => {
    const room = parseRoomInput(input);
    if (!room) return;
    join(room);
    window.dispatchEvent(new CustomEvent("kodama:open-room"));
  }, []);

  useEffect(() => {
    setIdentity(profile?.displayName || profile?.name, profile?.avatar);
  }, [profile?.displayName, profile?.name, profile?.avatar]);

  const { enqueue, setQueue } = player;
  useEffect(() => {
    const removeAdd = onRoomAdd(({ track, mode, from, fromId }) => {
      if (getTogether().isHost) enqueue({ ...track, addedBy: { id: fromId, name: from } }, mode);
    });
    const removeRemove = onRoomRemove(({ videoId }) => {
      if (getTogether().isHost)
        setQueue((queue) => queue.filter((track) => track.videoId !== videoId));
    });
    const switchProfile = () => leave();
    window.addEventListener("profile-switched", switchProfile);
    return () => {
      removeAdd();
      removeRemove();
      window.removeEventListener("profile-switched", switchProfile);
    };
  }, [enqueue, setQueue]);

  useEffect(
    () =>
      onRoomNotice((notice) => {
        if (notice.kind === "host" && notice.you) {
          const room = getTogether();
          setQueue([room.state?.track, ...room.queue].filter(Boolean));
        }
        const keys = {
          closed: "togetherClosed",
          kicked: "togetherKicked",
          full: "togetherFull",
          denied: "togetherDenied",
        };
        const key = keys[notice.kind];
        if (key) addToast?.(translate(localStorage.getItem("kiyoshi-lang") || "en", key), "info");
      }),
    [addToast, setQueue]
  );

  useEffect(() => {
    let cancelled = false;
    let unlisten = () => {};
    const handle = (url) => {
      if (/^kodama:\/\/together\//i.test(url)) joinRoom(url);
    };
    import("@tauri-apps/plugin-deep-link")
      .then(async ({ getCurrent, onOpenUrl }) => {
        const urls = await getCurrent();
        if (cancelled) return;
        urls?.forEach(handle);
        const cleanup = await onOpenUrl((links) => links.forEach(handle));
        if (cancelled) cleanup();
        else unlisten = cleanup;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      unlisten();
    };
  }, [joinRoom]);

  return { roomIntentRef, joinRoom };
}
