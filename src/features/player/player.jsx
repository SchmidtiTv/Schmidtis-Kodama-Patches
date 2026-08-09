import { useCallback, useEffect, useRef, useState } from "react";
import { getPlaylistMix } from "@/features/music/mix-api.js";
import { API } from "@/shared/api/client.js";
import { resolveMixTransitionPolicy } from "@/features/music/mix-transition-policy.js";
import { parseDurationToSeconds } from "@/features/lyrics/parse.js";
import { useAnimations } from "@/features/settings/display-context.jsx";
import { useAppearanceSettings } from "@/features/settings/settings-context.jsx";
import { useLang } from "@/shared/i18n/context.jsx";
import { useLyricsSettings } from "../settings/settings-context.jsx";
import {
  registerAudio as bpRegisterAudio,
  registerPlayerCommands as bpRegisterCommands,
  setNowPlaying as bpSetNowPlaying,
} from "@/features/player/player-bridge.js";
import { emitNowPlaying, EV_HELLO, EV_SHOW_MAIN } from "./miniplayer/bridge.js";
import { PlayerControls } from "./player-controls.jsx";
import { useSleepTimer } from "./hooks/use-sleep-timer.js";
import { useTrackMetadata } from "./hooks/use-track-metadata.js";
import {
  usePlaybackStatus,
  useQueueState,
  usePlaybackConfig,
  usePlayerActions,
} from "./player-context.jsx";
import { useDownloadState, useDownloadActions } from "../downloads/download-context.jsx";
import { useNativePlaybackEngine } from "./hooks/use-native-playback-engine.js";
import { shuffleQueueAfterCurrent } from "./shuffle-queue.js";
import { useVideoAudioSync } from "./hooks/use-video-audio-sync.js";
import {
  nextNative,
  pauseNative,
  playNative,
  previousNative,
  seekNative,
  setNativeLiked,
  setNativeRepeat,
  setNativeShuffle,
  setNativeVolume,
} from "./native-playback-engine.js";

export function Player({
  expanded,
  onExpandToggle,
  showLyrics,
  onToggleLyrics,
  videoAvailable = false,
  showVideoView = false,
  onSetVideoView,
  videoSync,
  queueOpen,
  onToggleQueue,
  fullscreen,
  onToggleFullscreen,
  onOpenAlbum,
  onOpenArtist,
  onRefetchLyrics,
  currentLyricsSource = "",
  onSwitchLyricsProvider,
  failedLyricsProviders = new Set(),
  language = "de",
  showLyricsTranslation = false,
  onToggleLyricsTranslation,
  lyricsTranslationLang = "DE",
  onSetLyricsTranslationLang,
  isCustomLyrics = false,
  onImportLyrics,
  onOpenLyricsBrowser,
  onRemoveCustomLyrics,
  onAddToPlaylist,
  buildShareLink,
}) {
  const { track, isPlaying, audioRef, restoredTrackId, playbackOrigin } = usePlaybackStatus();
  const { playerBarControls } = useAppearanceSettings();
  const { queue } = useQueueState();
  const { crossfade, crossfadeOverrides, playbackProgressive, mixTransitionsEnabled, mixTempoLockEnabled } = usePlaybackConfig();
  const { setQueue, setTrack, setIsPlaying, startSongRadio } = usePlayerActions();
  // Cached/downloading id sets + download/export/premium-detected actions come from
  // DownloadContext rather than props.
  const { cachedSongIds, downloadingIds } = useDownloadState();
  const {
    downloadSong: onDownloadSong,
    exportSong: onExportSong,
    markPremium: onPremiumDetected,
  } = useDownloadActions();
  // lyricsProviders is a settings preference, not player state — read the single source of
  // truth from SettingsContext instead of threading a duplicate copy through App.
  const { lyricsProviders } = useLyricsSettings();
  const [progress, setProgress] = useState(0);
  // Stable ref so fetchUrl can read the current playback mode without re-subscribing.
  const playbackProgressiveRef = useRef(playbackProgressive);
  playbackProgressiveRef.current = playbackProgressive;
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(() => {
    const saved = parseFloat(localStorage.getItem("kiyoshi-volume"));
    return isNaN(saved) ? 0.4 : Math.max(0, Math.min(1, saved));
  });
  const [streamUrl, setStreamUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isLiked, setIsLiked] = useState(false);
  const [mixTransitions, setMixTransitions] = useState([]);
  const [likePulsing, setLikePulsing] = useState(false);
  const [prevBouncing, setPrevBouncing] = useState(false);
  const [nextBouncing, setNextBouncing] = useState(false);
  const { sleepTimerEnd, setSleepTimerEnd, sleepRemaining, formatSleepRemaining } = useSleepTimer({
    audioRef,
    setIsPlaying,
  });
  const { fetchedBrowseIds, fetchMoreBrowseIds } = useTrackMetadata(track);

  const [shuffle, setShuffle] = useState(false);
  const [repeat, setRepeat] = useState("none");
  const t = useLang();
  const latestNowPlayingRef = useRef(null);
  const runPlaybackActionRef = useRef(null);

  // LRU cache: videoId -> url (max 50 entries, Map preserves insertion order)
  const URL_CACHE_MAX = 50;
  const urlCache = useRef(new Map());

  const repeatRef = useRef(repeat);
  const queueRef = useRef(queue);
  const trackRef = useRef(track);
  // A restored session should make the last song visible and ready to play, but reopening the
  // app must not unexpectedly begin audio. Consume the marker only for that exact track so a
  // user selecting another song while the restore is loading still starts it normally.
  const restoredTrackIdRef = useRef(restoredTrackId);
  const volumeRef = useRef(volume);
  const prevVolumeRef = useRef(volume > 0 ? volume : 0.4);

  useEffect(() => {
    const mixCollectionId =
      playbackOrigin?.kind === "mixCollection" ? playbackOrigin.mixCollectionId : null;
    if (!mixCollectionId) {
      setMixTransitions([]);
      return;
    }
    let cancelled = false;
    getPlaylistMix(mixCollectionId)
      .then((config) => {
        if (!cancelled) setMixTransitions(resolveMixTransitionPolicy(config, queue));
      })
      .catch(() => {
        if (!cancelled) setMixTransitions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [playbackOrigin, queue]);
  // Quadratic volume curve — human hearing is logarithmic, so v² feels linear
  const volCurve = (v) => v * v;

  const _lastProgressTs = useRef(0); // throttle: last time setProgress was called
  useEffect(() => {
    repeatRef.current = repeat;
  }, [repeat]);
  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);
  useEffect(() => {
    trackRef.current = track;
  }, [track]);
  useEffect(() => {
    volumeRef.current = volume;
  }, [volume]);

  const nativeAvailable = useNativePlaybackEngine({
    queue,
    track,
    restoredTrackId,
    shuffle,
    repeat,
    volume,
    crossfade,
    crossfadeOverrides,
    playbackProgressive,
    mixTransitionsEnabled,
    mixTempoLockEnabled,
    mixTransitions,
    showVideoView,
    queueRef,
    trackRef,
    setProgress,
    setDuration,
    setLoading,
    setIsPlaying,
    setTrack,
    setShuffle,
    setRepeat,
    setVolume,
  });

  useEffect(() => {
    if (nativeAvailable !== false) return;
    const audio = audioRef.current;
    if (!audio) return;
    const onVolumeChange = () => {
      const raw = audio.volume;
      const v = Math.sqrt(raw); // reverse the v² curve to get display value
      // Only update if the volume actually differs from current state to avoid
      // feedback loops (IpcAudio fires volumechange after every set volume).
      if (Math.abs(v - volumeRef.current) < 0.005) return;
      setVolume(v);
      if (v > 0) prevVolumeRef.current = v;
      localStorage.setItem("kiyoshi-volume", v);
    };
    audio.addEventListener("volumechange", onVolumeChange);
    return () => audio.removeEventListener("volumechange", onVolumeChange);
  }, [nativeAvailable]);

  const getAdjacentTrack = useCallback((dir) => {
    const q = queueRef.current;
    const t = trackRef.current;
    if (!q.length || !t) return null;
    const idx = q.findIndex((x) => x.videoId === t.videoId);
    if (idx === -1) return null;
    if (dir === "next") return q[(idx + 1) % q.length];
    return q[(idx - 1 + q.length) % q.length];
  }, []);

  // Update the ref before React commits so rapid skip bursts always advance from the track that
  // was just selected, rather than repeatedly reading the previous render's track.
  const goAdjacent = useCallback(
    (direction) => {
      if (nativeAvailable) {
        return direction === "next" ? nextNative() : previousNative();
      }
      const adjacentTrack = getAdjacentTrack(direction);
      if (adjacentTrack) {
        trackRef.current = adjacentTrack;
        setTrack(adjacentTrack);
      }
      return adjacentTrack;
    },
    [getAdjacentTrack, nativeAvailable, setTrack]
  );

  const urlCacheGet = (videoId) => {
    const c = urlCache.current;
    if (!c.has(videoId)) return null;
    // Move to end (most-recently-used)
    const val = c.get(videoId);
    c.delete(videoId);
    c.set(videoId, val);
    return val;
  };
  const urlCachePut = (videoId, url) => {
    const c = urlCache.current;
    c.delete(videoId); // remove old position if exists
    c.set(videoId, url);
    if (c.size > URL_CACHE_MAX) c.delete(c.keys().next().value); // evict oldest
  };

  const fetchUrl = useCallback(
    async (videoId) => {
      const cached = urlCacheGet(videoId);
      if (cached) return cached;
      // Prefer locally cached song (served via backend, works for both Rust & HTML5)
      try {
        const cr = await fetch(`${API}/song/cached/${videoId}`, { method: "HEAD" });
        if (cr.ok) {
          const cachedUrl = `${API}/song/cached/${videoId}`;
          urlCachePut(videoId, cachedUrl);
          return cachedUrl;
        }
      } catch {
        /* intentionally ignored */
      }
      const useRust = audioRef.current && audioRef.current._fallback === false;
      // Progressive (default): hand the Rust core the range-streaming proxy URL so it starts
      // playing as soon as the header is fetched, instead of waiting for a full yt-dlp download.
      if (useRust && playbackProgressiveRef.current) {
        const proxyUrl = `${API}/audio-stream/${videoId}`;
        urlCachePut(videoId, proxyUrl);
        return proxyUrl;
      }
      // Classic: download via yt-dlp to disk and return the file path (Rust reads from disk).
      if (useRust) {
        try {
          const r = await fetch(`${API}/stream-prepare/${videoId}`);
          const d = await r.json();
          if (d.premium_only) {
            onPremiumDetected?.(videoId);
            return null;
          }
          if (d.path) {
            // Prefix with file:// so Rust knows it's a local path
            const fileUrl = `file://${d.path.replace(/\\/g, "/")}`;
            urlCachePut(videoId, fileUrl);
            return fileUrl;
          }
        } catch (e) {
          console.error(`[stream-prepare] ${videoId}:`, e);
        }
      }
      // HTML5 fallback: fetch direct googlevideo URL (browser handles cookies)
      let lastStreamError = null;
      for (let i = 1; i <= 3; i++) {
        try {
          const r = await fetch(`${API}/stream/${videoId}`);
          const d = await r.json();
          if (d.premium_only) {
            onPremiumDetected?.(videoId);
            return null;
          }
          if (d.url) {
            urlCachePut(videoId, d.url);
            return d.url;
          }
          if (d.error) lastStreamError = d.error;
        } catch (e) {
          lastStreamError = String(e);
        }
        if (i < 3) await new Promise((res) => setTimeout(res, 800));
      }
      if (lastStreamError) console.error(`[stream] ${videoId}: ${lastStreamError}`);
      return null;
    },
    [onPremiumDetected]
  );

  useVideoAudioSync({
    enabled: nativeAvailable !== null,
    audioRef,
    trackRef,
    fetchUrl,
    trackId: track?.videoId,
    showVideoView,
    videoSync,
    setIsPlaying,
  });

  // Preload upcoming tracks in the background so sequential listening (album/playlist/queue)
  // has near-instant transitions and "next". Warm the next TWO tracks (most listening is
  // in order) plus the previous one. Sequential (not concurrent) to avoid starving the
  // current song's own download of bandwidth.
  const preloadAdjacent = useCallback(async () => {
    await new Promise((res) => setTimeout(res, 1500)); // let the current song's download get ahead
    const q = queueRef.current;
    const t = trackRef.current;
    if (!q.length || !t) return;
    const idx = q.findIndex((x) => x.videoId === t.videoId);
    if (idx === -1) return;
    const targets = [
      q[(idx + 1) % q.length],
      q[(idx + 2) % q.length],
      q[(idx - 1 + q.length) % q.length],
    ];
    for (const tk of targets) {
      if (!tk || tk.videoId === t.videoId) continue;
      if (playbackProgressiveRef.current) {
        // Progressive: prewarm the URL resolution (the ~2-4s yt-dlp extraction) so the next
        // play is extraction-free. No bytes are downloaded — playback streams on demand.
        try {
          await fetch(`${API}/audio-stream/${tk.videoId}/warm`);
        } catch {
          /* intentionally ignored */
        }
      } else if (!urlCache.current.has(tk.videoId)) {
        // Classic: pre-download to disk.
        try {
          await fetchUrl(tk.videoId);
        } catch {
          /* intentionally ignored */
        }
      }
    }
  }, [fetchUrl]);

  useEffect(() => {
    const videoId = track?.videoId;
    if (!videoId) return;
    let cancelled = false;
    // Check if track is liked
    queueMicrotask(() => setIsLiked(false));
    fetch(`${API}/liked/ids`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setIsLiked((d.ids || []).includes(videoId));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [track?.videoId]);
  useEffect(() => {
    setNativeLiked(isLiked);
  }, [isLiked, track?.videoId]);
  useEffect(() => {
    let unlisten = () => {};
    let cancelled = false;
    import("@tauri-apps/api/event")
      .then(({ listen }) =>
        listen("playback-liked-changed", ({ payload }) => {
          if (payload?.videoId === trackRef.current?.videoId) {
            setIsLiked(!!payload.liked);
          }
        })
      )
      .then((cleanup) => {
        if (cancelled) cleanup();
        else unlisten = cleanup;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      unlisten();
    };
  }, []);

  useEffect(() => {
    if (nativeAvailable !== false) return;
    if (!track) return;
    setLoading(true);
    setStreamUrl(null);
    let cancelled = false;

    fetchUrl(track.videoId).then((url) => {
      if (cancelled) return;
      if (url) {
        setStreamUrl(url);
      } else {
        console.error("Stream fehlgeschlagen");
      }
      setLoading(false);
    });

    preloadAdjacent();
    return () => {
      cancelled = true;
    };
  }, [nativeAvailable, preloadAdjacent, track]);

  useEffect(() => {
    if (nativeAvailable !== false) return;
    const a = audioRef.current;
    if (!a || !streamUrl) return;

    const shouldRemainPaused = restoredTrackIdRef.current === track?.videoId;
    restoredTrackIdRef.current = null;
    a.src = streamUrl;
    a.volume = volCurve(volume);
    volumeRef.current = volume;
    if (shouldRemainPaused) {
      a.pause();
      setIsPlaying(false);
    } else {
      a.play().catch((e) => console.error("[Player] play() error:", e));
      setIsPlaying(true);
    }
    setProgress(0);

    // IpcAudio may return 0 when Rust can't determine duration from metadata;
    // fall back to the track's formatted duration string in that case.
    const onDur = () => {
      const d = a.duration > 0 ? a.duration : parseDurationToSeconds(track?.duration) || 0;
      setDuration(d);
      setLoading(false);
    };

    const onEnd = () => {
      // Rust owns natural advancement. Keep the legacy path only for browser E2E and the
      // HTML-audio fallback, where no native PlaybackEngine is running.
      if (a._fallback !== false || a._e2eMedia) {
        if (repeatRef.current === "one") {
          a.currentTime = 0;
          a.play();
        } else {
          const next = getAdjacentTrack("next");
          if (next) setTrack(next);
          else if (repeatRef.current === "none") setIsPlaying(false);
        }
        return;
      }
      setIsPlaying(false);
    };

    // Rust owns transition timing; React only paints the coarse progress clock.
    const onTimeUpdate = () => {
      // Throttle setProgress to max 4× per second to avoid excessive re-renders.
      const now = performance.now();
      if (now - _lastProgressTs.current >= 250) {
        _lastProgressTs.current = now;
        setProgress(a.currentTime);
      }
    };

    // Always register listeners — even after a crossfade advance.
    a.addEventListener("timeupdate", onTimeUpdate);
    a.addEventListener("loadedmetadata", onDur);
    a.addEventListener("ended", onEnd);
    return () => {
      a.removeEventListener("timeupdate", onTimeUpdate);
      a.removeEventListener("loadedmetadata", onDur);
      a.removeEventListener("ended", onEnd);
    };
  }, [nativeAvailable, streamUrl, track?.duration, track?.videoId, volume]);

  const togglePlay = () => {
    if (nativeAvailable) {
      return isPlaying ? pauseNative() : playNative();
    }
    const a = audioRef.current;
    if (!a) return;
    if (isPlaying) {
      a.pause();
      setIsPlaying(false);
    } else {
      a.play();
      setIsPlaying(true);
    }
  };

  // Local/LAN commands still use the React controller. OS media controls bypass this path and
  // call the native PlaybackEngine directly.
  const mediaCtlRef = useRef({});
  mediaCtlRef.current = { togglePlay, goAdjacent, setTrack, setIsPlaying, queue };

  const cycleRepeat = () => {
    const nextRepeat = repeat === "none" ? "all" : repeat === "all" ? "one" : "none";
    if (nativeAvailable) {
      setNativeRepeat(nextRepeat);
    } else {
      setRepeat(nextRepeat);
    }
  };

  const toggleShuffle = () => {
    if (!shuffle) {
      setQueue((currentQueue) =>
        shuffleQueueAfterCurrent(currentQueue, trackRef.current?.videoId)
      );
    }
    if (nativeAvailable) {
      setNativeShuffle(!shuffle);
    } else {
      setShuffle(!shuffle);
    }
  };

  const seekTo = (position) => {
    if (nativeAvailable) {
      seekNative(position);
    } else if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, position);
    }
  };

  const setPlaybackVolume = (nextVolume) => {
    const normalized = Math.max(0, Math.min(1, nextVolume));
    setVolume(normalized);
    volumeRef.current = normalized;
    if (normalized > 0) prevVolumeRef.current = normalized;
    localStorage.setItem("kiyoshi-volume", String(normalized));
    if (nativeAvailable) {
      setNativeVolume(normalized);
    } else {
      if (audioRef.current) audioRef.current.volume = volCurve(normalized);
    }
  };

  const runPlaybackAction = (command) => {
    const h = mediaCtlRef.current;
    const action = typeof command === "string" ? command : command?.action;
    if (action === "playpause" || action === "toggle") h.togglePlay();
    else if (action === "next") h.goAdjacent("next");
    else if (action === "prev" || action === "previous") h.goAdjacent("prev");
    else if (action === "shuffle") toggleShuffle();
    else if (action === "repeat") cycleRepeat();
    else if (action === "like") h.toggleLike?.();
    else if (action === "seek" && typeof command.position === "number") {
      seekTo(command.position);
    } else if (action === "volume" && typeof command.value === "number") {
      setPlaybackVolume(command.value / 100);
    } else if (action === "queueJump" && command.videoId) {
      const selected = (h.queue || []).find((item) => item.videoId === command.videoId);
      if (selected) h.setTrack(selected);
    }
  };
  runPlaybackActionRef.current = runPlaybackAction;

  // The mini player lives in a separate webview, so it cannot use Big Picture's in-process
  // bridge. It receives a timestamped snapshot and uses the existing media-control channel
  // for commands, keeping this window the sole owner of the playback engine.
  useEffect(() => {
    let unlistenMedia = () => {};
    let unlistenHello = () => {};
    let unlistenShowMain = () => {};
    let cancelled = false;

    import("@tauri-apps/api/event")
      .then(async ({ listen }) => {
        const cleanups = await Promise.all([
          listen("media-control", ({ payload }) => runPlaybackActionRef.current?.(payload)),
          listen(EV_HELLO, () => {
            if (latestNowPlayingRef.current) emitNowPlaying(latestNowPlayingRef.current);
          }),
          listen(EV_SHOW_MAIN, async () => {
            const { getCurrentWindow } = await import("@tauri-apps/api/window");
            const window = getCurrentWindow();
            await window.show();
            await window.setFocus();
          }),
        ]);
        if (cancelled) cleanups.forEach((cleanup) => cleanup());
        else [unlistenMedia, unlistenHello, unlistenShowMain] = cleanups;
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      unlistenMedia();
      unlistenHello();
      unlistenShowMain();
    };
  }, []);
  // Big Picture bridge: expose playback commands (re-registered each render so they close over
  // current state) + push a formatted now-playing snapshot to the in-process store.
  useEffect(() => {
    bpRegisterCommands({
      action: runPlaybackAction,
      seek: seekTo,
    });
    bpRegisterAudio(audioRef.current); // hand the IpcAudio clock to Big Picture's lyrics view
  });
  useEffect(() => {
    const tr = track;
    const artists = Array.isArray(tr?.artists)
      ? tr.artists
          .map((a) => (a && a.name) || a)
          .filter(Boolean)
          .join(", ")
      : tr?.artists || "";
    const snapshot = {
      title: tr?.title || "",
      artists,
      thumbnail: tr?.thumbnail || "",
      isPlaying: !!isPlaying,
      position: Math.floor(progress || 0),
      duration: Math.floor(duration || 0),
      hasTrack: !!tr,
      shuffle: !!shuffle,
      repeat: repeat || "none",
      track: tr || null, // raw track object so Big Picture's lyrics view can fetch for it
      at: Date.now(),
    };
    latestNowPlayingRef.current = snapshot;
    bpSetNowPlaying(snapshot);
    emitNowPlaying(snapshot);
  }, [track, isPlaying, progress, duration, shuffle, repeat]);

  // Seek drag state for the HeroUI seek slider (seconds while dragging, else null).
  const [seekDrag, setSeekDrag] = useState(null);

  const toggleLike = async () => {
    if (!track) return;
    const newRating = isLiked ? "INDIFFERENT" : "LIKE";
    setIsLiked(!isLiked);
    if (!isLiked) {
      setLikePulsing(true);
      setTimeout(() => setLikePulsing(false), 450);
    }
    try {
      await fetch(`${API}/like/${track.videoId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rating: newRating,
          title: track.title || "",
          artists: track.artists || "",
          album: track.album || "",
          thumbnail: track.thumbnail || "",
          duration: track.duration || "",
        }),
      });
      // Last.fm Loved sync (backend no-ops if not connected)
      const lfArtist = (track.artists || "").replace(/\s*-\s*Topic$/i, "").trim();
      const lfTitle = (track.title || "").trim();
      if (lfArtist && lfTitle) {
        fetch(`${API}/lastfm/${newRating === "LIKE" ? "love" : "unlove"}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ artist: lfArtist, track: lfTitle }),
        }).catch(() => {});
      }
    } catch {
      setIsLiked(isLiked); // revert on error
    }
  };
  mediaCtlRef.current.toggleLike = toggleLike;

  const fmt = (s) => {
    if (!s || isNaN(s)) return "0:00";
    const m = Math.floor(s / 60),
      sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const anim = useAnimations();

  return (
    <PlayerControls
      {...{
        anim,
        audioRef,
        buildShareLink,
        cachedSongIds,
        currentLyricsSource,
        cycleRepeat,
        downloadingIds,
        duration,
        expanded,
        failedLyricsProviders,
        fetchMoreBrowseIds,
        fetchedBrowseIds,
        fmt,
        formatSleepRemaining,
        fullscreen,
        goAdjacent,
        isCustomLyrics,
        isLiked,
        isPlaying,
        language,
        likePulsing,
        loading,
        videoAvailable,
        showVideoView,
        onSetVideoView,
        lyricsProviders,
        lyricsTranslationLang,
        nextBouncing,
        onAddToPlaylist,
        onDownloadSong,
        onExpandToggle,
        onExportSong,
        onImportLyrics,
        onOpenLyricsBrowser,
        onOpenAlbum,
        onOpenArtist,
        onRefetchLyrics,
        onRemoveCustomLyrics,
        onSetLyricsTranslationLang,
        onStartSongRadio: startSongRadio,
        onSwitchLyricsProvider,
        onToggleFullscreen,
        onToggleLyrics,
        onToggleLyricsTranslation,
        onToggleQueue,
        prevBouncing,
        prevVolumeRef,
        progress,
        playerBarControls,
        queueOpen,
        repeat,
        seekDrag,
        setNextBouncing,
        setPrevBouncing,
        setSeekDrag,
        seekTo,
        setPlaybackVolume,
        setSleepTimerEnd,
        showLyrics,
        showLyricsTranslation,
        shuffle,
        sleepRemaining,
        sleepTimerEnd,
        t,
        toggleLike,
        togglePlay,
        toggleShuffle,
        track,
        volume,
      }}
    />
  );
}
