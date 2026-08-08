import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast, ToastProvider } from "@heroui/react";
import { API } from "@/shared/api/client.js";
import { native } from "@/shared/api/tauri.js";
import { thumb } from "@/shared/api/thumbnails.js";
import { AppShell } from "./AppShell.jsx";
import { GLOBAL_KEYFRAMES } from "./global-keyframes.js";
import {
  FfmpegSetupScreen,
  FfmpegUpdateBanner,
  LanguagePickerScreen,
  SplashScreen,
} from "./startup-screens.jsx";
import { storageCodecs, usePersistedState } from "@/shared/hooks/use-persisted-state.js";
import { setAccentSmooth, vibrantAccentFromImage } from "@/shared/lib/accent.js";
import {
  assignShortcut as resolveShortcutAssignment,
  CODE_DISPLAY_FALLBACK,
} from "@/shared/lib/shortcuts.js";
import { IS_MAC } from "@/shared/lib/platform.js";
import { useNetworkStatus } from "./hooks/use-network-status.js";
import { useObsOverlay } from "@/features/overlay/hooks/use-obs-overlay.js";
import { useRemoteControl } from "@/features/remote/hooks/use-remote-control.js";
import { useDownloadManager } from "@/features/downloads/hooks/use-download-manager.js";
import { useProfiles } from "@/features/profiles/hooks/use-profiles.js";
import { translate } from "@/shared/i18n/i18n.js";
import { getInitialLang } from "@/shared/lib/lang.js";
import { IconContext } from "@/shared/icons/icons.jsx";

import { LangContext } from "@/shared/i18n/context.jsx";
import {
  AnimationContext,
  FontScaleContext,
  TrackNumberContext,
  ZoomContext,
} from "@/features/settings/display-context.jsx";
import { DEFAULT_LYRICS_PROVIDERS, mergeLyricsProviders } from "@/features/lyrics/providers.js";
import { itemId, profileKey } from "@/features/music/lib/playlist-id.js";
import { useMusicNavigation } from "@/features/music/hooks/use-music-navigation.js";
import { useLikes } from "@/features/music/hooks/use-likes.js";
import { VIZ_DEFAULTS } from "@/features/player/player-ui.jsx";
import { usePlayerController } from "@/features/player/use-player-controller.js";
import { PlayerProvider } from "@/features/player/player-context.jsx";
import { ProfileProvider } from "@/features/profiles/profile-context.jsx";
import { DownloadProvider } from "@/features/downloads/download-context.jsx";
import { useLastfmClient } from "@/features/integrations/lastfm.js";
import { SettingsProviders } from "@/features/settings/settings-context.jsx";
import { DEFAULT_SHORTCUTS } from "@/features/settings/settings-constants.js";
import { useIpv4First } from "@/features/settings/use-ipv4-first.js";
import { useVideoSync } from "@/features/player/video-sync.jsx";
import {
  loadPlayerBarControls,
  togglePlayerBarControl,
} from "@/features/player/player-bar-preferences.js";

const CSS_FONT_SIZES = [10, 11, 12, 13, 14, 15, 16, 18, 20, 22];

const ZOOM_STEPS = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5];
const FONT_STEPS = [0.85, 0.93, 1.0, 1.1, 1.2, 1.35, 1.5];
const UI_ZOOM_STORAGE = {
  serialize: storageCodecs.number.serialize,
  deserialize: (raw) => {
    const value = storageCodecs.number.deserialize(raw);
    if (!ZOOM_STEPS.includes(value)) throw new TypeError("Stored zoom value is unsupported");
    return value;
  },
};
const FONT_SCALE_STORAGE = {
  serialize: storageCodecs.number.serialize,
  deserialize: (raw) => {
    const value = storageCodecs.number.deserialize(raw);
    if (!FONT_STEPS.includes(value)) throw new TypeError("Stored font scale is unsupported");
    return value;
  },
};

const APP_ICON_DEFAULT = "Kodama App Icon - Standard Pink.png";
const DevMenu = import.meta.env.DEV ? lazy(() => import("./dev-menu.jsx")) : null;

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const finishSplash = useCallback(() => setShowSplash(false), []);

  const [ffmpegSetupDone, setFfmpegSetupDone] = useState(
    () => localStorage.getItem("kiyoshi-ffmpeg-ok") === "1"
  );

  const [ffmpegUpdate, setFfmpegUpdate] = useState(null);
  useEffect(() => {
    if (!ffmpegSetupDone || !navigator.onLine) return;
    let cancelled = false;
    const tid = setTimeout(async () => {
      try {
        const d = await fetch(`${API}/ffmpeg/check-update`).then((r) => r.json());
        if (cancelled || !d.updateAvailable) return;
        if (localStorage.getItem("kiyoshi-ffmpeg-update-dismissed") === d.latest) return;
        setFfmpegUpdate({ installed: d.installed, latest: d.latest });
      } catch {
        /* intentionally ignored */
      }
    }, 6000);
    return () => {
      cancelled = true;
      clearTimeout(tid);
    };
  }, [ffmpegSetupDone]);

  const [pinnedIds, setPinnedIds] = useState([]);
  const [playerBarControls, setPlayerBarControls] = useState(loadPlayerBarControls);
  const handlePlayerBarControlToggle = useCallback(
    (control) => setPlayerBarControls((current) => togglePlayerBarControl(current, control)),
    []
  );

  const addToast = useCallback((message, type = "info") => {
    if (type === "error") toast.danger(message, { timeout: 6000 });
    else if (type === "success") toast.success(message, { timeout: 3500 });
    else toast(message, { timeout: 3500 });
  }, []);

  const togglePin = useCallback((pl) => {
    const stored = (() => {
      try {
        return JSON.parse(localStorage.getItem(profileKey("kiyoshi-pinned")) || "[]");
      } catch {
        return [];
      }
    })();
    const id = itemId(pl);
    const already = stored.find((p) => itemId(p) === id);
    const next = already ? stored.filter((p) => itemId(p) !== id) : [pl, ...stored];
    localStorage.setItem(profileKey("kiyoshi-pinned"), JSON.stringify(next));
    setPinnedIds(next.map((p) => itemId(p)));
    window.dispatchEvent(new Event("kiyoshi-pins-updated"));
  }, []);

  const [accent, setAccent] = useState(() => {
    const saved = localStorage.getItem("kiyoshi-accent");
    if (saved) document.documentElement.style.setProperty("--accent", saved);
    return saved || "#e040fb";
  });
  const [theme, setTheme] = useState(() => localStorage.getItem("kiyoshi-theme") || "dark");
  const [highContrast, setHighContrast] = useState(() => {
    const hc = localStorage.getItem("kiyoshi-high-contrast") === "true";
    if (hc) document.documentElement.setAttribute("data-highcontrast", "true");
    return hc;
  });
  const [appFont, setAppFont] = useState(() => {
    const saved = localStorage.getItem("kiyoshi-app-font") || "default";
    if (saved === "dyslexic")
      document.documentElement.style.setProperty("--font", "'OpenDyslexic', system-ui, sans-serif");
    return saved;
  });
  const handleAppFontChange = useCallback((id) => {
    setAppFont(id);
    localStorage.setItem("kiyoshi-app-font", id);
    if (id === "dyslexic") {
      document.documentElement.style.setProperty("--font", "'OpenDyslexic', system-ui, sans-serif");
    } else {
      document.documentElement.style.setProperty("--font", "'MiSans Latin', system-ui, sans-serif");
    }
  }, []);
  const [ambientVisualizer, setAmbientVisualizer] = useState(
    () => localStorage.getItem("kiyoshi-ambient-visualizer") !== "false"
  );
  const [instrumentalViz, setInstrumentalViz] = useState(
    () => localStorage.getItem("kiyoshi-instrumental-viz") !== "false"
  );
  const [vizConfig, setVizConfig] = useState(() => {
    try {
      return {
        ...VIZ_DEFAULTS,
        ...JSON.parse(localStorage.getItem("kiyoshi-visualizer-config") || "{}"),
      };
    } catch {
      return { ...VIZ_DEFAULTS };
    }
  });
  const updateViz = useCallback(
    (patch) =>
      setVizConfig((c) => {
        const next = { ...c, ...patch };
        localStorage.setItem("kiyoshi-visualizer-config", JSON.stringify(next));
        return next;
      }),
    []
  );
  const [ambientBackground, setAmbientBackground] = useState(
    () => localStorage.getItem("kiyoshi-ambient-bg") === "true"
  );

  const flashbangTriggerRef = useRef(null);
  const lightClickRef = useRef({ count: 0, lastTime: 0 });

  const [accentDynamic, setAccentDynamic] = useState(
    () => localStorage.getItem("kiyoshi-accent-dynamic") === "true"
  );
  const handleAccentDynamicChange = useCallback((on) => {
    setAccentDynamic(on);
    localStorage.setItem("kiyoshi-accent-dynamic", on ? "true" : "false");
  }, []);
  const [accentSat, setAccentSat] = useState(() => {
    const v = parseFloat(localStorage.getItem("kiyoshi-accent-sat"));
    return isNaN(v) ? 0.5 : v;
  });
  const [accentLight, setAccentLight] = useState(() => {
    const v = parseFloat(localStorage.getItem("kiyoshi-accent-light"));
    return isNaN(v) ? 0.6 : v;
  });
  const handleAccentSatChange = useCallback((v) => {
    setAccentSat(v);
    localStorage.setItem("kiyoshi-accent-sat", String(v));
  }, []);
  const handleAccentLightChange = useCallback((v) => {
    setAccentLight(v);
    localStorage.setItem("kiyoshi-accent-light", String(v));
  }, []);

  const handleAccentChange = useCallback(
    (color) => {
      setAccent(color);
      if (!accentDynamic) document.documentElement.style.setProperty("--accent", color);
      localStorage.setItem("kiyoshi-accent", color);
    },
    [accentDynamic]
  );

  const handleThemeChange = useCallback((t) => {
    setTheme(t);
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("kiyoshi-theme", t);
    if (t === "light") {
      const now = Date.now();
      if (now - lightClickRef.current.lastTime < 700) {
        lightClickRef.current.count++;
        if (lightClickRef.current.count >= 4) {
          lightClickRef.current.count = 0;
          flashbangTriggerRef.current?.();
        }
      } else {
        lightClickRef.current.count = 1;
      }
      lightClickRef.current.lastTime = now;
    } else {
      lightClickRef.current.count = 0;
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  const [searchQuery, setSearchQuery] = useState("");

  const {
    view,
    setView,
    appKey,
    setAppKey,
    viewRefreshKey,
    setViewRefreshKey,
    collection,
    setCollection,
    artistView,
    handleSearch,
    removeRecentPlaylist,
    openPlaylist,
    openAlbum,
    openArtist,
    navigateTo,
    goBack,
  } = useMusicNavigation({ setSearchQuery });

  const resetLyricsSessionRef = useRef(null);

  const playerIntegrationRef = useRef({
    discordRpc: true,
    discordStatusDisplay: "song",
    youtubeHistoryEnabled: false,
    remoteEnabled: false,
  });
  const lastfm = useLastfmClient();
  const player = usePlayerController({
    addToast,
    resetLyricsSessionRef,
    integrationsRef: playerIntegrationRef,
  });
  const {
    audioRef,
    currentTrack,
    setCurrentTrack,
    isPlaying,
    stopPlayback,
    setQueue,
    crossfade,
    setCrossfade,
    playbackProgressive,
    setPlaybackProgressive,
    mixTransitionsEnabled,
    setMixTransitionsEnabled,
    mixTempoLockEnabled,
    setMixTempoLockEnabled,
    crossfadeOverrides,
    removeCrossfadeOverride,
    refreshNativeIntegrations,
  } = player;
  const [discordRpc, setDiscordRpc] = useState(
    () => localStorage.getItem("kiyoshi-discord-rpc") !== "false"
  );
  const [discordStatusDisplay, setDiscordStatusDisplay] = useState(
    () => localStorage.getItem("kiyoshi-discord-status-display") || "song"
  );
  const [ytmusicHistorySync, setYtmusicHistorySync] = useState(
    () => localStorage.getItem("kiyoshi-ytmusic-history-sync") === "true"
  );
  const [videoSyncEnabled, setVideoSyncEnabled] = useState(
    () => localStorage.getItem("kiyoshi-video-sync") === "true"
  );
  const [videoSyncQuality, setVideoSyncQuality] = useState(
    () => localStorage.getItem("kiyoshi-video-sync-quality") || "auto"
  );
  const [videoLyricsStyle, setVideoLyricsStyle] = useState(
    () => localStorage.getItem("kiyoshi-video-lyrics-style") || "split"
  );
  const [videoViewTrackId, setVideoViewTrackId] = useState(null);
  const videoSync = useVideoSync(
    currentTrack?.videoId,
    videoSyncEnabled,
    videoSyncQuality === "auto" ? null : Number(videoSyncQuality)
  );
  const showVideoView = videoSync.ready && videoViewTrackId === currentTrack?.videoId;
  const setShowVideoView = useCallback(
    (visible) => setVideoViewTrackId(visible ? currentTrack?.videoId || null : null),
    [currentTrack?.videoId]
  );

  useEffect(() => {
    if (!accentDynamic) {
      document.documentElement.style.setProperty("--accent", accent);
      return;
    }
    const url = currentTrack?.thumbnail ? thumb(currentTrack.thumbnail) : null;
    if (!url) {
      document.documentElement.style.setProperty("--accent", accent);
      return;
    }
    let cancelled = false;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      if (cancelled) return;
      try {
        setAccentSmooth(vibrantAccentFromImage(img, accentSat, accentLight));
      } catch {
        document.documentElement.style.setProperty("--accent", accent);
      }
    };
    img.onerror = () => {
      if (!cancelled) document.documentElement.style.setProperty("--accent", accent);
    };
    img.src = url;
    return () => {
      cancelled = true;
    };
  }, [accentDynamic, currentTrack?.thumbnail, accent, accentSat, accentLight]);

  const usageSecRef = useRef(Number(localStorage.getItem("kiyoshi-total-usage") || 0));
  const playtimeSecRef = useRef(Number(localStorage.getItem("kiyoshi-total-playtime") || 0));

  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState === "visible") {
        usageSecRef.current += 1;
        if (usageSecRef.current % 30 === 0)
          localStorage.setItem("kiyoshi-total-usage", String(usageSecRef.current));
      }
    }, 1000);
    const flush = () => localStorage.setItem("kiyoshi-total-usage", String(usageSecRef.current));
    window.addEventListener("beforeunload", flush);
    return () => {
      flush();
      clearInterval(id);
      window.removeEventListener("beforeunload", flush);
    };
  }, []);

  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => {
      playtimeSecRef.current += 1;
      if (playtimeSecRef.current % 15 === 0)
        localStorage.setItem("kiyoshi-total-playtime", String(playtimeSecRef.current));
    }, 1000);
    return () => {
      localStorage.setItem("kiyoshi-total-playtime", String(playtimeSecRef.current));
      clearInterval(id);
    };
  }, [isPlaying]);

  const [closeTray, setCloseTray] = useState(
    () => localStorage.getItem("kiyoshi-close-tray") !== "false"
  );
  useEffect(() => {
    native.setCloseToTray(closeTray).catch(() => {});
  }, [closeTray]);

  const { obsEnabled, obsPort, obsPortInput, setObsPortInput, toggleObs, saveObsPort } =
    useObsOverlay();
  useEffect(() => {
    playerIntegrationRef.current = {
      discordRpc,
      discordStatusDisplay,
      lastfmConnected: lastfm.connected,
      youtubeHistoryEnabled: ytmusicHistorySync,
      remoteEnabled: playerIntegrationRef.current.remoteEnabled,
    };
    refreshNativeIntegrations();
  }, [
    discordRpc,
    discordStatusDisplay,
    lastfm.connected,
    ytmusicHistorySync,
    refreshNativeIntegrations,
  ]);
  const [overlayOpen, setOverlayOpen] = useState(false);

  const [showLyricsTranslation, setShowLyricsTranslation] = useState(
    () => localStorage.getItem("kiyoshi-lyrics-translation") === "true"
  );
  const [lyricsTranslationLang, setLyricsTranslationLang] = useState(
    () => localStorage.getItem("kiyoshi-lyrics-translation-lang") || "DE"
  );
  const [showRomaji, setShowRomaji] = useState(
    () => localStorage.getItem("kiyoshi-lyrics-romaji") === "true"
  );
  const [syllableZoom, setSyllableZoom] = useState(
    () => localStorage.getItem("kiyoshi-lyrics-syllable-zoom") === "true"
  );
  const [fluidLyrics, setFluidLyrics] = useState(
    () => localStorage.getItem("kiyoshi-lyrics-fluid") === "true"
  );

  const [showAgentTags, setShowAgentTags] = useState(
    () => localStorage.getItem("kiyoshi-lyrics-agent-tags") !== "false"
  );
  const [showLyrics, setShowLyrics] = useState(true);
  const autoCoverRef = useRef(false);
  const [queueOpen, setQueueOpen] = useState(false);

  const [language, setLanguage] = useState(() => getInitialLang());

  const downloads = useDownloadManager({ addToast, language });
  const { downloadBatches, downloadQueueMin, setDownloadQueueMin, handleCancelBatch } = downloads;

  const [animations, setAnimations] = useState(
    () => localStorage.getItem("kiyoshi-animations") !== "false"
  );

  const [lyricsFontSize, setLyricsFontSize] = useState(() => {
    const s = parseInt(localStorage.getItem("kiyoshi-lyrics-font-size"));
    return isNaN(s) ? 32 : s;
  });
  const [lyricsTranslationFontSize, setLyricsTranslationFontSize] = useState(() => {
    const s = parseInt(localStorage.getItem("kiyoshi-lyrics-translation-font-size"));
    return isNaN(s) ? 20 : s;
  });
  const [lyricsRomajiFontSize, setLyricsRomajiFontSize] = useState(() => {
    const s = parseInt(localStorage.getItem("kiyoshi-lyrics-romaji-font-size"));
    return isNaN(s) ? 18 : s;
  });
  const [hideExplicit, setHideExplicit] = useState(
    () => localStorage.getItem("kiyoshi-hide-explicit") === "true"
  );
  const [showTrackNumbers, setShowTrackNumbers] = useState(
    () => localStorage.getItem("kodama-track-numbers") === "true"
  );
  const handleTrackNumbersChange = useCallback((on) => {
    setShowTrackNumbers(on);
    localStorage.setItem("kodama-track-numbers", String(on));
  }, []);

  const [anonStats, setAnonStats] = useState(
    () => localStorage.getItem("kodama-anon-stats") !== "false"
  );
  const handleAnonStatsChange = useCallback((on) => {
    setAnonStats(on);
    localStorage.setItem("kodama-anon-stats", String(on));
  }, []);
  const [hideUserHandle, setHideUserHandle] = useState(
    () => localStorage.getItem("kiyoshi-hide-handle") === "true"
  );
  const [uiZoom, setUiZoom] = usePersistedState("kiyoshi-ui-zoom", 1.0, UI_ZOOM_STORAGE);

  const [customShortcuts, setCustomShortcuts] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("kiyoshi-shortcuts") || "{}");
      return { ...DEFAULT_SHORTCUTS, ...saved };
    } catch {
      return { ...DEFAULT_SHORTCUTS };
    }
  });
  const [shortcutsEnabled, setShortcutsEnabled] = useState(
    () => localStorage.getItem("kiyoshi-shortcuts-enabled") !== "false"
  );
  const [shortcutLabels, setShortcutLabels] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("kiyoshi-shortcut-labels") || "{}");
    } catch {
      return {};
    }
  });
  const [recordingShortcut, setRecordingShortcut] = useState(null);
  const customShortcutsRef = useRef(customShortcuts);
  const recordingShortcutRef = useRef(null);
  useEffect(() => {
    customShortcutsRef.current = customShortcuts;
  }, [customShortcuts]);
  useEffect(() => {
    recordingShortcutRef.current = recordingShortcut;
  }, [recordingShortcut]);

  const getShortcutParts = useCallback(
    (stored) => {
      if (!stored) return [];
      if (!stored.includes("+")) {
        const savedLabel = shortcutLabels[stored];
        const label =
          savedLabel?.length === 1 && savedLabel.trim()
            ? savedLabel
            : CODE_DISPLAY_FALLBACK[stored] || stored;
        return [label.length === 1 ? label.toUpperCase() : label];
      }

      const parts = stored.split("+");
      const code = parts[parts.length - 1];
      const mods = parts.slice(0, -1).map((modifier) => {
        if (!IS_MAC) return modifier === "Meta" ? "Super" : modifier;
        return {
          Meta: "⌘",
          Alt: "⌥",
          Shift: "⇧",
          Ctrl: "⌃",
        }[modifier];
      });
      const savedLabel = shortcutLabels[code];
      const keyLabel =
        savedLabel?.length === 1 && savedLabel.trim()
          ? savedLabel
          : CODE_DISPLAY_FALLBACK[code] || code;
      const displayKey = keyLabel.length === 1 ? keyLabel.toUpperCase() : keyLabel;
      return [...mods, displayKey];
    },
    [shortcutLabels]
  );

  const resetShortcut = useCallback((id) => {
    setCustomShortcuts((prev) => {
      const next = { ...prev, [id]: DEFAULT_SHORTCUTS[id] };
      localStorage.setItem("kiyoshi-shortcuts", JSON.stringify(next));
      return next;
    });
  }, []);
  const assignShortcut = useCallback((id, shortcut) => {
    setCustomShortcuts((prev) => {
      const next = resolveShortcutAssignment(prev, id, shortcut);
      localStorage.setItem("kiyoshi-shortcuts", JSON.stringify(next));
      return next;
    });
  }, []);
  const disableShortcut = useCallback((id) => {
    setCustomShortcuts((prev) => {
      const next = { ...prev, [id]: null };
      localStorage.setItem("kiyoshi-shortcuts", JSON.stringify(next));
      return next;
    });
    setRecordingShortcut((current) => (current === id ? null : current));
  }, []);
  const resetAllShortcuts = useCallback(() => {
    setCustomShortcuts({ ...DEFAULT_SHORTCUTS });
    setRecordingShortcut(null);
    localStorage.removeItem("kiyoshi-shortcuts");
  }, []);
  const handleShortcutsEnabledChange = useCallback((enabled) => {
    setShortcutsEnabled(enabled);
    setRecordingShortcut(null);
    localStorage.setItem("kiyoshi-shortcuts-enabled", String(enabled));
  }, []);

  const [appFontScale, setAppFontScale] = usePersistedState(
    "kiyoshi-font-scale",
    1.0,
    FONT_SCALE_STORAGE
  );

  useLayoutEffect(() => {
    CSS_FONT_SIZES.forEach((s) => {
      document.documentElement.style.setProperty(`--t${s}`, `${Math.round(s * appFontScale)}px`);
    });
  }, [appFontScale]);

  const [lyricsProviders, setLyricsProviders] = useState(() => {
    try {
      const saved = localStorage.getItem("kiyoshi-lyrics-providers");
      if (saved) return mergeLyricsProviders(JSON.parse(saved));
    } catch {
      /* intentionally ignored */
    }
    return DEFAULT_LYRICS_PROVIDERS;
  });

  useEffect(() => {
    setLyricsProviders((current) => {
      const merged = mergeLyricsProviders(current);
      if (JSON.stringify(merged) === JSON.stringify(current)) return current;
      localStorage.setItem("kiyoshi-lyrics-providers", JSON.stringify(merged));
      return merged;
    });
  }, []);
  const { ipv4First, toggleIpv4First } = useIpv4First();

  const {
    remoteEnabled,
    remoteInfo,
    remoteDevices,
    remoteTrustedIds,
    pairModalOpen,
    setPairModalOpen,
    toggleRemote,
    remoteDeviceAction,
    remoteRememberDevice,
  } = useRemoteControl();
  useEffect(() => {
    playerIntegrationRef.current = {
      ...playerIntegrationRef.current,
      remoteEnabled,
    };
    refreshNativeIntegrations();
  }, [remoteEnabled, refreshNativeIntegrations]);

  const [appIcon, setAppIcon] = useState(
    () => localStorage.getItem("kodama-app-icon") || APP_ICON_DEFAULT
  );
  const [appIconCustomizationAvailable, setAppIconCustomizationAvailable] = useState(
    () => !IS_MAC
  );
  useEffect(() => {
    let active = true;
    native
      .appIconCustomizationAvailable()
      .then((available) => {
        if (active) setAppIconCustomizationAvailable(available);
      })
      .catch(() => {
        if (active) setAppIconCustomizationAvailable(true);
      });
    return () => {
      active = false;
    };
  }, []);
  const applyAppIcon = useCallback(async (file) => {
    if (!appIconCustomizationAvailable) return;
    try {
      await native.setAppIcon(file);
    } catch (e) {
      console.error("[AppIcon] set failed:", e);
    }
  }, [appIconCustomizationAvailable]);
  const handleAppIconChange = useCallback(
    (file) => {
      if (!appIconCustomizationAvailable) return;
      setAppIcon(file);
      localStorage.setItem("kodama-app-icon", file);
      applyAppIcon(file);
    },
    [appIconCustomizationAvailable, applyAppIcon]
  );

  useEffect(() => {
    const stored = localStorage.getItem("kodama-app-icon");
    if (appIconCustomizationAvailable && stored && stored !== APP_ICON_DEFAULT) {
      applyAppIcon(stored);
    }
  }, [appIconCustomizationAvailable, applyAppIcon]);

  const profile = useProfiles({
    setPinnedIds,
    setView,
    setSearchQuery,
    setAppKey,
    setCurrentTrack,
    setQueue,
    setCollection,
    setOverlayOpen,
    setQueueOpen,
    stopPlayback,
  });

  const {
    profiles,
    showLogin,
    setShowLogin,
    showLangPicker,
    setShowLangPicker,
    showProfileSwitcher,
    setShowProfileSwitcher,
    switchingTo,
    addingProfile,
    setAddingProfile,
    reauthName,
    setReauthName,
    fetchProfiles,
  } = profile;

  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API}/status`).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const { likedIds, handleToggleLike } = useLikes({ lastfm });

  const { offlineMode, isActuallyOffline, isOffline } = useNetworkStatus({
    fetchProfiles,
    setAppKey,
    setView,
  });

  const handleLanguageChange = (lang) => {
    setLanguage(lang);
    localStorage.setItem("kiyoshi-lang", lang);
    native
      .updateTrayLabels(translate(lang, "trayShow"), translate(lang, "trayQuit"))
      .catch(() => {});
  };

  useEffect(() => {
    const lang = getInitialLang();
    native
      .updateTrayLabels(translate(lang, "trayShow"), translate(lang, "trayQuit"))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const onWheel = (e) => {
      const audio = audioRef.current;
      if (!audio) return;

      const playerBar = e.target.closest?.("[data-volume-area]");
      if (!playerBar) return;
      e.preventDefault();
      const delta = e.deltaY < 0 ? 0.02 : -0.02;
      const dv = Math.min(1, Math.max(0, Math.sqrt(audio.volume) + delta));
      audio.volume = dv * dv;
    };
    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
  }, [audioRef]);

  const appearanceSettings = useMemo(
    () => ({
      accent,
      onAccentChange: handleAccentChange,
      accentDynamic,
      onAccentDynamicChange: handleAccentDynamicChange,
      accentSat,
      onAccentSatChange: handleAccentSatChange,
      accentLight,
      onAccentLightChange: handleAccentLightChange,
      appIcon,
      appIconCustomizationAvailable,
      onAppIconChange: handleAppIconChange,
      theme,
      onThemeChange: handleThemeChange,
      animations,
      onAnimationsChange: (v) => {
        setAnimations(v);
        localStorage.setItem("kiyoshi-animations", v);
      },
      highContrast,
      onToggleHighContrast: () => {
        const next = !highContrast;
        setHighContrast(next);
        document.documentElement.setAttribute("data-highcontrast", String(next));
        localStorage.setItem("kiyoshi-high-contrast", String(next));
      },
      appFont,
      onAppFontChange: handleAppFontChange,
      appFontScale,
      onFontScaleChange: (v) => {
        setAppFontScale(v);
      },
      uiZoom,
      onUiZoomChange: (v) => {
        setUiZoom(v);
      },
      showTrackNumbers,
      onTrackNumbersChange: handleTrackNumbersChange,
      hideExplicit,
      onHideExplicitChange: (v) => {
        setHideExplicit(v);
        localStorage.setItem("kiyoshi-hide-explicit", v);
      },
      ambientBackground,
      onToggleAmbientBackground: () => {
        const next = !ambientBackground;
        setAmbientBackground(next);
        localStorage.setItem("kiyoshi-ambient-bg", String(next));
      },
      ambientVisualizer,
      onToggleAmbientVisualizer: () => {
        const next = !ambientVisualizer;
        setAmbientVisualizer(next);
        localStorage.setItem("kiyoshi-ambient-visualizer", String(next));
      },
      instrumentalViz,
      onToggleInstrumentalViz: (v) => {
        setInstrumentalViz(v);
        localStorage.setItem("kiyoshi-instrumental-viz", v ? "true" : "false");
        if (!v && autoCoverRef.current) {
          autoCoverRef.current = false;
          setShowLyrics(true);
        }
      },
      vizConfig,
      onUpdateViz: updateViz,
      vizPreviewTrack: currentTrack,
      vizPreviewPlaying: isPlaying,
      playerBarControls,
      onPlayerBarControlToggle: handlePlayerBarControlToggle,
    }),
    [
      accent,
      handleAccentChange,
      accentDynamic,
      handleAccentDynamicChange,
      accentSat,
      handleAccentSatChange,
      accentLight,
      handleAccentLightChange,
      appIcon,
      appIconCustomizationAvailable,
      handleAppIconChange,
      theme,
      handleThemeChange,
      animations,
      highContrast,
      appFont,
      handleAppFontChange,
      appFontScale,
      setAppFontScale,
      uiZoom,
      setUiZoom,
      showTrackNumbers,
      handleTrackNumbersChange,
      hideExplicit,
      ambientBackground,
      ambientVisualizer,
      instrumentalViz,
      vizConfig,
      updateViz,
      currentTrack,
      isPlaying,
      playerBarControls,
      handlePlayerBarControlToggle,
    ]
  );

  const playbackSettings = useMemo(
    () => ({
      autoplay: player.autoplay,
      onAutoplayChange: player.setAutoplay,
      crossfade,
      onCrossfadeChange: setCrossfade,
      crossfadeOverrides,
      crossfadeQueue: player.queue,
      crossfadeDisabled: showVideoView,
      onRemoveCrossfadeOverride: removeCrossfadeOverride,
      playbackProgressive,
      onPlaybackProgressiveChange: setPlaybackProgressive,
      mixTransitionsEnabled,
      onMixTransitionsEnabledChange: setMixTransitionsEnabled,
      mixTempoLockEnabled,
      onMixTempoLockEnabledChange: setMixTempoLockEnabled,
      videoSyncEnabled,
      onToggleVideoSync: () => {
        const next = !videoSyncEnabled;
        setVideoSyncEnabled(next);
        localStorage.setItem("kiyoshi-video-sync", String(next));
      },
      videoSyncQuality,
      onVideoSyncQualityChange: (value) => {
        setVideoSyncQuality(value);
        localStorage.setItem("kiyoshi-video-sync-quality", value);
      },
      videoLyricsStyle,
      onVideoLyricsStyleChange: (value) => {
        setVideoLyricsStyle(value);
        localStorage.setItem("kiyoshi-video-lyrics-style", value);
      },
    }),
    [
      player.autoplay,
      player.setAutoplay,
      crossfade,
      setCrossfade,
      crossfadeOverrides,
      player.queue,
      showVideoView,
      removeCrossfadeOverride,
      playbackProgressive,
      setPlaybackProgressive,
      mixTransitionsEnabled,
      setMixTransitionsEnabled,
      mixTempoLockEnabled,
      setMixTempoLockEnabled,
      videoSyncEnabled,
      videoSyncQuality,
      videoLyricsStyle,
    ]
  );

  const lyricsSettings = useMemo(
    () => ({
      lyricsFontSize,
      onLyricsFontSizeChange: (v) => {
        setLyricsFontSize(v);
        localStorage.setItem("kiyoshi-lyrics-font-size", v);
      },
      lyricsTranslationFontSize,
      onLyricsTranslationFontSizeChange: (v) => {
        setLyricsTranslationFontSize(v);
        localStorage.setItem("kiyoshi-lyrics-translation-font-size", v);
      },
      lyricsRomajiFontSize,
      onLyricsRomajiFontSizeChange: (v) => {
        setLyricsRomajiFontSize(v);
        localStorage.setItem("kiyoshi-lyrics-romaji-font-size", v);
      },
      lyricsProviders,
      onLyricsProvidersChange: (v) => {
        setLyricsProviders(v);
        localStorage.setItem("kiyoshi-lyrics-providers", JSON.stringify(v));
      },
      showRomaji,
      onToggleRomaji: () => {
        const next = !showRomaji;
        setShowRomaji(next);
        localStorage.setItem("kiyoshi-lyrics-romaji", String(next));
      },
      showAgentTags,
      onToggleAgentTags: () => {
        const next = !showAgentTags;
        setShowAgentTags(next);
        localStorage.setItem("kiyoshi-lyrics-agent-tags", String(next));
      },
      syllableZoom,
      onToggleSyllableZoom: () => {
        const next = !syllableZoom;
        setSyllableZoom(next);
        localStorage.setItem("kiyoshi-lyrics-syllable-zoom", String(next));
      },
      fluidLyrics,
      onToggleFluidLyrics: () => {
        const next = !fluidLyrics;
        setFluidLyrics(next);
        localStorage.setItem("kiyoshi-lyrics-fluid", String(next));
      },
    }),
    [
      lyricsFontSize,
      lyricsTranslationFontSize,
      lyricsRomajiFontSize,
      lyricsProviders,
      showRomaji,
      showAgentTags,
      syllableZoom,
      fluidLyrics,
    ]
  );

  const integrationSettings = useMemo(
    () => ({
      closeTray,
      onCloseTrayChange: (v) => {
        setCloseTray(v);
        localStorage.setItem("kiyoshi-close-tray", String(v));
        native.setCloseToTray(v).catch(() => {});
      },
      discordRpc,
      onDiscordRpcChange: (v) => {
        setDiscordRpc(v);
        localStorage.setItem("kiyoshi-discord-rpc", v);
        if (!v) native.clearDiscordRpc().catch(() => {});
      },
      discordStatusDisplay,
      onDiscordStatusDisplayChange: (v) => {
        setDiscordStatusDisplay(v);
        localStorage.setItem("kiyoshi-discord-status-display", v);
      },
      ytmusicHistorySync,
      onYtmusicHistorySyncChange: (v) => {
        setYtmusicHistorySync(v);
        localStorage.setItem("kiyoshi-ytmusic-history-sync", String(v));
      },
      ipv4First,
      onIpv4FirstChange: toggleIpv4First,
      obsEnabled,
      obsPort,
      obsPortInput,
      setObsPortInput,
      toggleObs,
      onObsPortSave: saveObsPort,
      remoteEnabled,
      remoteDevices,
      remoteTrustedIds,
      onToggleRemote: toggleRemote,
      onRemoteDevice: remoteDeviceAction,
      onRememberDevice: remoteRememberDevice,
      onPairDevice: () => setPairModalOpen(true),
    }),
    [
      closeTray,
      discordRpc,
      discordStatusDisplay,
      ytmusicHistorySync,
      ipv4First,
      toggleIpv4First,
      obsEnabled,
      obsPort,
      obsPortInput,
      setObsPortInput,
      toggleObs,
      saveObsPort,
      remoteEnabled,
      remoteDevices,
      remoteTrustedIds,
      toggleRemote,
      remoteDeviceAction,
      remoteRememberDevice,
      setPairModalOpen,
    ]
  );

  const shortcutSettings = useMemo(
    () => ({
      customShortcuts,
      shortcutsEnabled,
      recordingShortcut,
      setRecordingShortcut,
      getShortcutParts,
      assignShortcut,
      disableShortcut,
      resetShortcut,
      resetAllShortcuts,
      onShortcutsEnabledChange: handleShortcutsEnabledChange,
    }),
    [
      customShortcuts,
      shortcutsEnabled,
      recordingShortcut,
      getShortcutParts,
      assignShortcut,
      disableShortcut,
      resetShortcut,
      resetAllShortcuts,
      handleShortcutsEnabledChange,
    ]
  );

  const appShellNav = {
    view,
    setView,
    appKey,
    viewRefreshKey,
    setViewRefreshKey,
    collection,
    setCollection,
    artistView,
    searchQuery,
    handleSearch,
    removeRecentPlaylist,
    openPlaylist,
    openAlbum,
    openArtist,
    navigateTo,
    goBack,
    pinnedIds,
    togglePin,
  };
  const appShellUi = {
    overlayOpen,
    setOverlayOpen,
    queueOpen,
    setQueueOpen,
    showLyrics,
    setShowLyrics,
    uiZoom,
    setUiZoom,
    videoSync,
    showVideoView,
    setShowVideoView,
    videoLyricsStyle,
  };
  const appShellShortcuts = {
    customShortcutsRef,
    recordingShortcutRef,
    shortcutsEnabled,
    searchShortcutParts: shortcutsEnabled ? getShortcutParts(customShortcuts.openSearch) : [],
    assignShortcut,
    setShortcutLabels,
    setRecordingShortcut,
  };
  const appShellAppearancePrefs = {
    animations,
    hideExplicit,
    ambientBackground,
    ambientVisualizer,
    vizConfig,
    instrumentalViz,
  };
  const appShellLyricsPrefs = {
    lyricsFontSize,
    lyricsProviders,
    showLyricsTranslation,
    setShowLyricsTranslation,
    lyricsTranslationLang,
    setLyricsTranslationLang,
    lyricsTranslationFontSize,
    showRomaji,
    lyricsRomajiFontSize,
    showAgentTags,
    syllableZoom,
    fluidLyrics,
  };
  const appShellAuthGate = {
    showLogin,
    setShowLogin,
    addingProfile,
    setAddingProfile,
    reauthName,
    setReauthName,
    showProfileSwitcher,
    setShowProfileSwitcher,
    switchingTo,
  };
  const appShellRemote = {
    remoteEnabled,
    remoteInfo,
    remoteDevices,
    pairModalOpen,
    setPairModalOpen,
    remoteDeviceAction,
    remoteRememberDevice,
  };
  const appShellNetwork = { offlineMode, isActuallyOffline, isOffline };
  const appShellDownloadQueue = {
    downloadBatches,
    downloadQueueMin,
    setDownloadQueueMin,
    handleCancelBatch,
  };
  const appShellPrivacySettings = {
    anonStats,
    handleAnonStatsChange,
    hideUserHandle,
    setHideUserHandle,
  };
  const appShellBridges = { autoCoverRef, flashbangTriggerRef, resetLyricsSessionRef };

  return (
    <IconContext.Provider value={{ weight: "bold" }}>
      <LangContext.Provider value={language}>
        <TrackNumberContext.Provider value={showTrackNumbers}>
          <AnimationContext.Provider value={animations}>
            <FontScaleContext.Provider value={appFontScale}>
              <ZoomContext.Provider value={uiZoom}>
                <ProfileProvider controller={profile}>
                  <DownloadProvider controller={downloads}>
                    <PlayerProvider controller={player}>
                      <SettingsProviders
                        appearance={appearanceSettings}
                        playback={playbackSettings}
                        lyrics={lyricsSettings}
                        integrations={integrationSettings}
                        shortcuts={shortcutSettings}
                      >
                        <style>{GLOBAL_KEYFRAMES}</style>
                        {!animations && (
                          <style>{`*, *::before, *::after { transition: none !important; animation: none !important; }`}</style>
                        )}
                        {showSplash && (
                          <SplashScreen animations={animations} onComplete={finishSplash} />
                        )}
                        {/* Language picker first on very first launch, before FFmpeg setup */}
                        {showLangPicker && !showLogin && (
                          <LanguagePickerScreen
                            currentLanguage={language}
                            onConfirm={(lang) => {
                              localStorage.setItem("kiyoshi-lang", lang);
                              setLanguage(lang);
                              setShowLangPicker(false);
                              if (!profiles.length) setShowLogin(true);
                            }}
                          />
                        )}
                        {!ffmpegSetupDone && !showLangPicker && (
                          <FfmpegSetupScreen onDone={() => setFfmpegSetupDone(true)} />
                        )}
                        {ffmpegUpdate && (
                          <FfmpegUpdateBanner
                            installed={ffmpegUpdate.installed}
                            latest={ffmpegUpdate.latest}
                            onClose={() => setFfmpegUpdate(null)}
                          />
                        )}

                        {/* Toast Notifications */}
                        <ToastProvider
                          placement="bottom end"
                          className="bottom-[120px]! z-[100000]!"
                        />

                        <Suspense fallback={null}>
                          {DevMenu && <DevMenu player={player} addToast={addToast} />}
                        </Suspense>

                        <AppShell
                          language={language}
                          addToast={addToast}
                          handleLanguageChange={handleLanguageChange}
                          obsEnabled={obsEnabled}
                          likedIds={likedIds}
                          handleToggleLike={handleToggleLike}
                          nav={appShellNav}
                          shellUi={appShellUi}
                          shortcuts={appShellShortcuts}
                          appearancePrefs={appShellAppearancePrefs}
                          lyricsPrefs={appShellLyricsPrefs}
                          authGate={appShellAuthGate}
                          remote={appShellRemote}
                          network={appShellNetwork}
                          downloadQueue={appShellDownloadQueue}
                          privacySettings={appShellPrivacySettings}
                          bridges={appShellBridges}
                        />
                      </SettingsProviders>
                    </PlayerProvider>
                  </DownloadProvider>
                </ProfileProvider>
              </ZoomContext.Provider>
            </FontScaleContext.Provider>
          </AnimationContext.Provider>
        </TrackNumberContext.Provider>
      </LangContext.Provider>
    </IconContext.Provider>
  );
}
