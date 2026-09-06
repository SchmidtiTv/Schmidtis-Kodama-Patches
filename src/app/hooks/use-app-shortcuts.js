import { useEffect, useRef } from "react";
import { matchesShortcut, serializeShortcut } from "@/shared/lib/shortcuts.js";
import { IS_MAC } from "@/shared/lib/platform.js";

const ZOOM_STEPS = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5];

export function useAppShortcuts({
  recordingShortcutRef,
  customShortcutsRef,
  shortcutsEnabled,
  audioRef,
  queueRef,
  assignShortcut,
  setShortcutLabels,
  setRecordingShortcut,
  setIsPlaying,
  setCurrentTrack,
  toggleFullscreen,
  setOverlayOpen,
  setQueueOpen,
  setSplitView,
  setShowLyricsManual,
  setUiZoom,
  openFeedback,
  openSettings,
  openSearch,
  toggleSidebar,
  navigateTo,
  currentTrack,
  overlayOpen,
  splitView,
}) {
  const mutePrevVolumeRef = useRef(0.5);
  useEffect(() => {
    const onKey = (e) => {
      const tgt = e.target;
      const isModifier = ["Control", "Shift", "Alt", "Meta"].includes(e.key);

      // Recording must run before the dialog/input guard because the shortcut editor itself lives
      // inside Settings. Capture the next non-modifier key and keep it from activating focused UI.
      if (recordingShortcutRef.current) {
        if (isModifier || e.repeat) return;
        e.preventDefault();
        e.stopPropagation();
        if (e.code !== "Escape") {
          assignShortcut(recordingShortcutRef.current, serializeShortcut(e));
          setShortcutLabels((prev) => {
            if (e.key.length !== 1 || !e.key.trim() || prev[e.code] === e.key) return prev;
            const next = { ...prev, [e.code]: e.key };
            localStorage.setItem("kiyoshi-shortcut-labels", JSON.stringify(next));
            return next;
          });
        }
        setRecordingShortcut(null);
        return;
      }

      if (
        tgt.tagName === "INPUT" ||
        tgt.tagName === "TEXTAREA" ||
        tgt.isContentEditable ||
        (tgt.closest && tgt.closest('[role="menu"],[role="dialog"],[role="menuitem"]'))
      )
        return;

      // Capture layout-aware display labels on every keypress
      if (!isModifier && e.code && e.key.length === 1 && e.key.trim()) {
        setShortcutLabels((prev) => {
          if (prev[e.code] === e.key) return prev;
          const next = { ...prev, [e.code]: e.key };
          localStorage.setItem("kiyoshi-shortcut-labels", JSON.stringify(next));
          return next;
        });
      }

      // While the overlay editor is open, playback shortcuts must not fire.
      if (document.querySelector("[data-overlay-editor]")) return;
      // Same for Big Picture mode.
      if (document.querySelector("[data-bigpicture]")) return;

      // Escape remains a standard dismiss action even when custom shortcuts are disabled.
      if (e.code === "Escape") {
        setOverlayOpen(false);
        setQueueOpen(false);
        return;
      }
      if (!shortcutsEnabled) return;

      const sc = customShortcutsRef.current;
      const nativeZoomModifier = IS_MAC ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey;
      const nativeZoomIn =
        sc.zoomIn === `${IS_MAC ? "Meta" : "Ctrl"}+Equal` &&
        nativeZoomModifier &&
        !e.altKey &&
        (e.code === "Equal" || e.code === "NumpadAdd");
      const nativeZoomOut =
        sc.zoomOut === `${IS_MAC ? "Meta" : "Ctrl"}+Minus` &&
        nativeZoomModifier &&
        !e.altKey &&
        !e.shiftKey &&
        (e.code === "Minus" || e.code === "NumpadSubtract");

      if (matchesShortcut(sc.openSearch, e)) {
        e.preventDefault();
        openSearch();
      } else if (matchesShortcut(sc.openSettings, e)) {
        e.preventDefault();
        openSettings();
      } else if (matchesShortcut(sc.toggleSidebar, e)) {
        e.preventDefault();
        toggleSidebar();
      } else if (matchesShortcut(sc.toggleQueue, e)) {
        e.preventDefault();
        setQueueOpen((open) => !open);
      } else if (matchesShortcut(sc.feedback, e)) {
        e.preventDefault();
        openFeedback();
      } else if (matchesShortcut(sc.goHome, e)) {
        e.preventDefault();
        navigateTo("home");
      } else if (matchesShortcut(sc.openLibrary, e)) {
        e.preventDefault();
        navigateTo("library");
      } else if (matchesShortcut(sc.openLiked, e)) {
        e.preventDefault();
        navigateTo("liked");
      } else if (matchesShortcut(sc.openHistory, e)) {
        e.preventDefault();
        navigateTo("history");
      } else if (matchesShortcut(sc.openDownloads, e)) {
        e.preventDefault();
        navigateTo("downloads");
      } else if (matchesShortcut(sc.playPause, e)) {
        e.preventDefault();
        if (audioRef.current) {
          if (audioRef.current.paused) {
            audioRef.current.play();
            setIsPlaying(true);
          } else {
            audioRef.current.pause();
            setIsPlaying(false);
          }
        }
      } else if (matchesShortcut(sc.nextTrack, e)) {
        e.preventDefault();
        const q = queueRef.current;
        setCurrentTrack((t) => {
          if (!t) return t;
          const idx = q.findIndex((x) => x.videoId === t.videoId);
          return idx < q.length - 1 ? q[idx + 1] : t;
        });
      } else if (matchesShortcut(sc.prevTrack, e)) {
        e.preventDefault();
        const q = queueRef.current;
        setCurrentTrack((t) => {
          if (!t) return t;
          const idx = q.findIndex((x) => x.videoId === t.videoId);
          return idx > 0 ? q[idx - 1] : t;
        });
      } else if (matchesShortcut(sc.volUp, e)) {
        e.preventDefault();
        if (audioRef.current) {
          const dv = Math.min(1, Math.sqrt(audioRef.current.volume) + 0.02);
          audioRef.current.volume = dv * dv;
        }
      } else if (matchesShortcut(sc.volDown, e)) {
        e.preventDefault();
        if (audioRef.current) {
          const dv = Math.max(0, Math.sqrt(audioRef.current.volume) - 0.02);
          audioRef.current.volume = dv * dv;
        }
      } else if (matchesShortcut(sc.fullscreen, e)) {
        e.preventDefault();
        if (!e.repeat) void toggleFullscreen();
      } else if (matchesShortcut(sc.mute, e)) {
        e.preventDefault();
        if (audioRef.current) {
          if (audioRef.current.volume > 0) {
            mutePrevVolumeRef.current = audioRef.current.volume;
            audioRef.current.volume = 0;
          } else {
            audioRef.current.volume = mutePrevVolumeRef.current || 0.5;
          }
        }
      } else if (matchesShortcut(sc.lyrics, e)) {
        e.preventDefault();
        if (!currentTrack) return;
        if (overlayOpen) {
          if (splitView) {
            setSplitView(false);
            setShowLyricsManual(true);
          } else setShowLyricsManual((l) => !l);
        } else {
          setOverlayOpen(true);
        }
      } else if (matchesShortcut(sc.seekBack, e)) {
        e.preventDefault();
        if (audioRef.current)
          audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - 5);
      } else if (matchesShortcut(sc.seekForward, e)) {
        e.preventDefault();
        if (audioRef.current)
          audioRef.current.currentTime = Math.min(
            audioRef.current.duration || 0,
            audioRef.current.currentTime + 5
          );
      } else if (matchesShortcut(sc.zoomIn, e) || nativeZoomIn) {
        e.preventDefault();
        setUiZoom((z) => {
          const idx = ZOOM_STEPS.indexOf(z);
          const next = ZOOM_STEPS[Math.min(ZOOM_STEPS.length - 1, idx >= 0 ? idx + 1 : 2)];
          return next;
        });
      } else if (matchesShortcut(sc.zoomOut, e) || nativeZoomOut) {
        e.preventDefault();
        setUiZoom((z) => {
          const idx = ZOOM_STEPS.indexOf(z);
          const next = ZOOM_STEPS[Math.max(0, idx >= 0 ? idx - 1 : 2)];
          return next;
        });
      }
    };
    // capture:true so we intercept before the WebView can handle Ctrl+= etc.
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [
    audioRef,
    assignShortcut,
    currentTrack,
    customShortcutsRef,
    navigateTo,
    openFeedback,
    openSearch,
    openSettings,
    overlayOpen,
    queueRef,
    recordingShortcutRef,
    setCurrentTrack,
    toggleFullscreen,
    setIsPlaying,
    setOverlayOpen,
    setQueueOpen,
    setRecordingShortcut,
    setShortcutLabels,
    setShowLyricsManual,
    setSplitView,
    setUiZoom,
    shortcutsEnabled,
    splitView,
    toggleSidebar,
  ]);
}
