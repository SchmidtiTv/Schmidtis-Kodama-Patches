import { useCallback, useEffect, useRef, useState } from "react";
import {
  getNativeSnapshot,
  listenForNativeProgress,
  listenForNativeStateChanges,
  listenForNativeTrackChanges,
  preloadNative,
  replaceNativeQueue,
  restartNative,
  setNativeCurrentTrack,
  setNativeUiVisible,
  setNativeVolume,
  updateNativeTransitionPolicy,
  updateNativeTransport,
} from "../native-playback-engine.js";

export function useNativePlaybackEngine({
  queue,
  track,
  restoredTrackId,
  shuffle,
  repeat,
  volume,
  crossfade,
  crossfadeOverrides,
  playbackProgressive,
  mixTransitions,
  mixTransitionsEnabled,
  mixTempoLockEnabled,
  showVideoView,
  queueRef,
  trackRef,
  setProgress,
  setDuration,
  setLoading,
  setBuffered,
  setIsPlaying,
  setTrack,
  setShuffle,
  setRepeat,
  setVolume,
}) {
  const [nativeAvailable, setNativeAvailable] = useState(null);
  const syncedTrackRef = useRef(null);
  const initialTrackRef = useRef(track?.videoId || null);
  const preferencesSyncedRef = useRef(false);

  const applySnapshot = useCallback(
    (snapshot) => {
      if (!snapshot?.status) return;
      setIsPlaying(snapshot.status === "playing" || snapshot.status === "loading");
      setLoading(snapshot.status === "loading");
      if (Number.isFinite(snapshot.positionSeconds)) {
        setProgress(snapshot.positionSeconds);
      }
      if (Number.isFinite(snapshot.durationSeconds)) {
        setDuration(snapshot.durationSeconds);
      }
      if (preferencesSyncedRef.current) {
        if (typeof snapshot.shuffle === "boolean") {
          setShuffle(snapshot.shuffle);
        }
        if (["none", "all", "one"].includes(snapshot.repeat)) {
          setRepeat(snapshot.repeat);
        }
        if (Number.isFinite(snapshot.volume)) {
          setVolume(Math.round(snapshot.volume * 1000) / 1000);
        }
      }
    },
    [setDuration, setIsPlaying, setLoading, setProgress, setRepeat, setShuffle, setVolume]
  );

  useEffect(() => {
    let cancelled = false;
    getNativeSnapshot().then((snapshot) => {
      if (cancelled) return;
      const available = snapshot !== null;
      setNativeAvailable(available);
      if (available) applySnapshot(snapshot);
    });
    return () => {
      cancelled = true;
    };
  }, [applySnapshot]);

  useEffect(() => {
    const syncVisibility = () => {
      const visible = document.visibilityState === "visible";
      setNativeUiVisible(visible).then((snapshot) => {
        if (visible && snapshot) applySnapshot(snapshot);
      });
    };
    syncVisibility();
    document.addEventListener("visibilitychange", syncVisibility);
    return () => {
      document.removeEventListener("visibilitychange", syncVisibility);
      setNativeUiVisible(false);
    };
  }, [applySnapshot]);

  useEffect(() => {
    if (!nativeAvailable) return;
    replaceNativeQueue(queue);
  }, [nativeAvailable, queue]);

  useEffect(() => {
    if (!nativeAvailable || syncedTrackRef.current === track) return;
    let cancelled = false;
    const syncSelection = async () => {
      const videoId = track?.videoId || null;
      if (videoId) setProgress(0);
      const queueSnapshot = await replaceNativeQueue(queue);
      if (cancelled || !queueSnapshot) return;
      const snapshot = await setNativeCurrentTrack(track);
      if (cancelled || !snapshot) return;
      syncedTrackRef.current = track;
      if (!videoId) return;
      const isRestoredSelection =
        initialTrackRef.current === videoId && restoredTrackId === videoId;
      initialTrackRef.current = null;
      if (isRestoredSelection) {
        await preloadNative();
      } else {
        // A previous source can still report Playing between set_current_track (which marks the
        // selection Stopped) and the next command. player_play would then keep that old source,
        // making a deliberate selection appear to require a second click. Restart always builds
        // the selected track's source, whether this is a new track or a re-selection.
        await restartNative();
      }
    };
    syncSelection();
    return () => {
      cancelled = true;
    };
  }, [nativeAvailable, queue, restoredTrackId, setProgress, track]);

  useEffect(() => {
    if (!nativeAvailable) return;
    Promise.all([updateNativeTransport({ shuffle, repeat }), setNativeVolume(volume)]).then(() => {
      preferencesSyncedRef.current = true;
    });
  }, [nativeAvailable, shuffle, repeat, volume]);

  useEffect(() => {
    if (!nativeAvailable) return;
    updateNativeTransitionPolicy({
      crossfade,
      crossfadeOverrides,
      queue,
      playbackProgressive,
      automaticCrossfade: !showVideoView,
      mixTransitions,
      mixTransitionsEnabled,
      mixTempoLockEnabled,
    });
  }, [crossfade, crossfadeOverrides, mixTempoLockEnabled, mixTransitions, mixTransitionsEnabled, nativeAvailable, playbackProgressive, queue, showVideoView]);

  useEffect(() => {
    let unlisten = () => {};
    let cancelled = false;
    listenForNativeTrackChanges(({ track: nativeTrack, reason } = {}) => {
      if (!nativeTrack?.videoId) return;
      // Local selection has already updated React state before it asks Rust to play/restart.
      // A delayed echo for the previously playing track must not roll that choice back; native
      // navigation and external controls use distinct reasons and continue through below.
      if (reason === "play" || reason === "restart") return;
      const nextTrack =
        queueRef.current.find((item) => item.videoId === nativeTrack.videoId) ||
        (trackRef.current?.videoId === nativeTrack.videoId ? trackRef.current : nativeTrack);

      if (trackRef.current?.videoId === nativeTrack.videoId) {
        syncedTrackRef.current = trackRef.current;
        return;
      }
      syncedTrackRef.current = nextTrack;
      trackRef.current = nextTrack;
      setProgress(0);
      setTrack(nextTrack);
    }).then((cleanup) => {
      if (cancelled) cleanup();
      else unlisten = cleanup;
    });
    return () => {
      cancelled = true;
      unlisten();
    };
  }, [queueRef, setProgress, setTrack, trackRef]);

  useEffect(() => {
    let unlisten = () => {};
    let cancelled = false;
    listenForNativeStateChanges(applySnapshot).then((cleanup) => {
      if (cancelled) cleanup();
      else unlisten = cleanup;
    });
    return () => {
      cancelled = true;
      unlisten();
    };
  }, [applySnapshot]);

  useEffect(() => {
    let unlisten = () => {};
    let cancelled = false;
    listenForNativeProgress((progress) => {
      if (Number.isFinite(progress?.position)) setProgress(progress.position);
      if (Number.isFinite(progress?.duration)) setDuration(progress.duration);
      if (typeof progress?.paused === "boolean") setIsPlaying(!progress.paused);
      // null for anything not streamed over the network (local files and classic downloads are
      // already complete), which is the signal for the seek bar to leave the indicator off.
      setBuffered(typeof progress?.buffered === "number" ? progress.buffered : null);
      setLoading(false);
    }).then((cleanup) => {
      if (cancelled) cleanup();
      else unlisten = cleanup;
    });
    return () => {
      cancelled = true;
      unlisten();
    };
  }, [setBuffered, setDuration, setIsPlaying, setLoading, setProgress]);

  return nativeAvailable;
}
