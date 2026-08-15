import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Button, ChipLabel, ChipRoot } from "@heroui/react";
import { openUrl } from "@tauri-apps/plugin-opener";

import { CaretDown, UploadSimple } from "@/shared/icons/icons.jsx";
import { API } from "@/shared/api/client.js";
import { thumb } from "@/shared/api/thumbnails.js";
import { translate, isRtlLang, isRtlText, hasJapaneseText } from "@/shared/i18n/i18n.js";
import { useLang } from "@/shared/i18n/context.jsx";
import {
  parseLrc,
  parseTtml,
  parseDurationToSeconds,
  prepareLyrics,
  findTimestampIndex,
} from "@/features/lyrics/parse.js";
import { paintLineWords } from "@/features/lyrics/paint.js";
import { fetchLyrics } from "@/features/lyrics/fetch.js";
import { DEFAULT_LYRICS_PROVIDERS } from "@/features/lyrics/providers.js";
import { LyricsBrowserModal } from "@/features/lyrics/lyrics-browser-modal.jsx";
import { LyricsToolChips, OffsetChips, SourceChip } from "@/features/lyrics/lyrics-tool-chips.jsx";
import { useLyricOffset } from "@/features/lyrics/lyric-offset.js";
import { openComposer } from "./composer-window.js";
import { sustainedWordScale } from "./sustained-line.js";

const FLUID_DRIFT_WINDOW = 6;
// How much the active line grows in fluid mode. Needed as a constant because a translation
// aligned to the growing edge has to be pulled back by exactly this amount.
const LYRIC_ZOOM = 1.06;

// A different track or explicit refetch is a new lyrics session. Resetting at this boundary
// keeps transient fetch/animation state local to the session instead of synchronously clearing
// several state values from an effect.
export function LyricsOverlay(props) {
  const sessionKey = `${props.track?.videoId ?? "none"}:${props.refetchKey ?? 0}:${props.forcedProvider ?? "all"}`;
  return <LyricsOverlayContent key={sessionKey} {...props} />;
}

function LyricsOverlayContent({
  track,
  audioRef,
  fontSize = 32,
  providers = DEFAULT_LYRICS_PROVIDERS,
  refetchKey = 0,
  onAddToast,
  language = "de",
  forcedProvider = null,
  onSourceChange,
  onProviderFailed,
  showTranslation = false,
  onToggleTranslation,
  translationLang = "DE",
  translationFontSize = 20,
  showRomaji = false,
  onToggleRomaji,
  romajiFontSize = 18,
  onCustomLyricsStatusChange,
  importLyricsRef,
  removeCustomLyricsRef,
  openLyricsBrowserRef,
  showAgentTags = true,
  ambientVisualizer = true,
  syllableZoom = false,
  fluidLyrics = false,
  ambientBackground = false,
  fullscreen = false,
  playerBarVisible = false,
  onInstrumentalChange,
  isActive = true,
  isPlaying = true,
}) {
  // In fullscreen the player bar overlays the bottom of the lyrics view; lift the
  // bottom-anchored chips above it while it's visible so they aren't covered.
  const chipBottomLift = fullscreen && playerBarVisible ? 104 : 0;
  const [lyrics, setLyrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState("");
  const [submitterName, setSubmitterName] = useState(null);
  const [browserOpen, setBrowserOpen] = useState(false);
  // Identifies the exact version currently shown (Unison submission id), so the browser
  // can mark the right one active when two versions share text + submitter.
  const [appliedVersionId, setAppliedVersionId] = useState(null);

  // Apply a specific version chosen from the lyrics browser, and remember it for this
  // song via the same per-video cache the normal fetch uses.
  const applyLyricsVersion = (r) => {
    if (!r?.lrc) return;
    setLyrics(r.lrc);
    setSource(r.source);
    setSubmitterName(r.submitterName || null);
    setAppliedVersionId(r.id ?? null);
    onSourceChange?.(r.source);
    try {
      localStorage.setItem(
        `kiyoshi-lyrics-${track?.videoId}`,
        JSON.stringify({
          lrc: r.lrc,
          source: r.source,
          submitterName: r.submitterName || null,
          versionId: r.id ?? null,
          failedIds: [],
        })
      );
    } catch {
      /* intentionally ignored */
    }
  };
  // The active line affects the React tree. Per-word timing stays in refs so the rAF loop can
  // paint syllables without turning every animation frame into a React render.
  const [activeIdx, setActiveIdx] = useState(-1);
  const [translationResult, setTranslationResult] = useState(null);
  const [romajiResult, setRomajiResult] = useState(null);
  const [isCustomLyrics, setIsCustomLyrics] = useState(false);
  const [customLyricsKey, setCustomLyricsKey] = useState(0);
  const [, setInGap] = useState(false);
  const [trailingIdx, setTrailingIdx] = useState(-1); // previous line still visible after new line starts
  const [scrollActive, setScrollActive] = useState(false); // auto-hide scrollbar (hover + idle)
  const [userScrollingTrackId, setUserScrollingTrackId] = useState(null);
  const userScrolling = userScrollingTrackId === track?.videoId;
  const userScrollingRef = useRef(false);
  const t = useLang();
  // Per-song timing correction, shared with the video-sync captions view via lyric-offset.js.
  const { offset, offsetRef, adjustOffset } = useLyricOffset(track?.videoId);
  const lyricTextLines = useMemo(() => {
    if (!lyrics) return [];
    return lyrics.map((line) => {
      const main = line.wordSync ? (line.words || []).map((w) => w.text).join("") : line.text || "";
      const bg = (line.bgWords || []).map((w) => w.text).join("") || line.bgText || "";
      return bg ? `${main} ${bg}` : main;
    });
  }, [lyrics]);
  // Romaji only makes sense for Japanese script — otherwise the button would sit there doing
  // nothing on every English song. Checked across the whole lyric, since a single line may be
  // Latin even in a Japanese song.
  const romanizable = useMemo(
    () => lyricTextLines.some((line) => hasJapaneseText(line)),
    [lyricTextLines]
  );
  const translationKey = useMemo(
    () => `${translationLang}\u001f${lyricTextLines.join("\u001e")}`,
    [translationLang, lyricTextLines]
  );
  const romajiKey = useMemo(() => lyricTextLines.join("\u001e"), [lyricTextLines]);
  const translations =
    showTranslation && translationResult?.key === translationKey ? translationResult.lines : null;
  const romajiLines = showRomaji && romajiResult?.key === romajiKey ? romajiResult.lines : null;
  const containerRef = useRef(null);
  const scrollIdleRef = useRef(null);

  // Reveal the scrollbar on cursor activity, then auto-hide after a short idle.
  const wakeScrollbar = useCallback(() => {
    setScrollActive(true);
    if (scrollIdleRef.current) clearTimeout(scrollIdleRef.current);
    scrollIdleRef.current = setTimeout(() => setScrollActive(false), 3200);
  }, []);
  const sleepScrollbar = useCallback(() => {
    if (scrollIdleRef.current) clearTimeout(scrollIdleRef.current);
    // Linger before sliding out instead of snapping away on mouse-leave.
    scrollIdleRef.current = setTimeout(() => setScrollActive(false), 1600);
  }, []);
  useEffect(
    () => () => {
      if (scrollIdleRef.current) clearTimeout(scrollIdleRef.current);
    },
    []
  );
  // Briefly reveal the source badge (+ scrollbar) once lyrics have loaded, then let it idle-hide.
  useEffect(() => {
    if (!source) return;
    const frame = requestAnimationFrame(wakeScrollbar);
    return () => cancelAnimationFrame(frame);
  }, [source, wakeScrollbar]);
  const rafRef = useRef(null);
  const lyricsDataRef = useRef(null); // rAF loop reads lyrics without closure
  const syncedRef = useRef(false); // whether the current lyrics have real timestamps (not plain)
  const lastIdxRef = useRef(-1); // tracks active line to detect changes
  const playbackLineIdxRef = useRef(-1); // timestamp index; independent from gap display state
  const playbackJumpRef = useRef(true); // seeked/audio discontinuity needs a binary re-sync
  const prevTRef = useRef(0); // previous loop time — to detect backward seeks/restarts
  const inGapRef = useRef(false); // tracks inter-line gap state without closure
  const instVizRef = useRef(false); // tracks instrumental-segment state without closure
  const onInstChangeRef = useRef(onInstrumentalChange); // live prop for the rAF loop
  useEffect(() => {
    onInstChangeRef.current = onInstrumentalChange;
  });
  const trailingIdxRef = useRef(-1); // mirror of trailingIdx for RAF access without stale closure
  const wordElsRef = useRef([]); // DOM refs to active line's word spans
  const sustainedWordElsRef = useRef([]); // per-word visual-only sustained-vocal scale targets
  const sustainedWordRef = useRef(null); // current target, cleared as the timed word changes
  const activeWordIdxRef = useRef(-1); // tracks active word within line
  const activeWordMaxRef = useRef(-1); // highest syllable already zoomed (dedupes the pop)
  const trailWordElsRef = useRef([]); // DOM refs to trailing line's word spans
  const activeTrailWordIdxRef = useRef(-1); // tracks active word within the trailing line
  const syllableZoomRef = useRef(syllableZoom); // read live in the rAF loop without re-subscribing
  useEffect(() => {
    syllableZoomRef.current = syllableZoom;
  }, [syllableZoom]);
  const fluidLyricsRef = useRef(fluidLyrics); // live read in the word-paint rAF (for the word glow)
  useEffect(() => {
    fluidLyricsRef.current = fluidLyrics;
  }, [fluidLyrics]);
  const bgContainerRef = useRef(null); // DOM ref to bg-vocals container (RAF-controlled opacity)
  // High-resolution playback time: interpolate between timeupdate events
  const audioSnapRef = useRef({ ct: 0, pt: 0, playing: false });

  // Keep lyricsDataRef in sync with state
  useEffect(() => {
    lyricsDataRef.current = prepareLyrics(lyrics);
    // Plain (unsynced) lyrics have time -1 on every line; only treat as synced if at least one
    // line carries a real timestamp.
    syncedRef.current = !!(lyrics && lyrics.some((l) => (l.time ?? -1) >= 0));
    playbackLineIdxRef.current = -1;
    playbackJumpRef.current = true;
  }, [lyrics]);

  // Fetch translations when showTranslation is enabled, lyrics change, or target language changes
  useEffect(() => {
    if (!showTranslation || lyricTextLines.length === 0) return;
    let cancelled = false;
    fetch("http://localhost:9847/translate-lyrics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lines: lyricTextLines, target_lang: translationLang }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        setTranslationResult({ key: translationKey, lines: d.translations || null });
      })
      .catch(() => {
        if (!cancelled) setTranslationResult({ key: translationKey, lines: null });
      });
    return () => {
      cancelled = true;
    };
  }, [showTranslation, lyricTextLines, translationLang, translationKey]);

  // Fetch Romaji when toggle is enabled or lyrics change
  useEffect(() => {
    if (!showRomaji || lyricTextLines.length === 0) return;
    let cancelled = false;
    fetch("http://localhost:9847/romanize-lyrics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lines: lyricTextLines }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        setRomajiResult({ key: romajiKey, lines: d.romanizations || null });
      })
      .catch(() => {
        if (!cancelled) setRomajiResult({ key: romajiKey, lines: null });
      });
    return () => {
      cancelled = true;
    };
  }, [showRomaji, lyricTextLines, romajiKey]);

  // Sync audio snap so the rAF loop can interpolate currentTime at 60 fps
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const snap = (event) => {
      if (event?.type === "seeked") playbackJumpRef.current = true;
      audioSnapRef.current = {
        ct: audio.currentTime,
        pt: performance.now(),
        playing: !audio.paused,
      };
    };
    audio.addEventListener("timeupdate", snap);
    audio.addEventListener("play", snap);
    audio.addEventListener("pause", snap);
    audio.addEventListener("seeked", snap);
    snap(); // initial
    return () => {
      audio.removeEventListener("timeupdate", snap);
      audio.removeEventListener("play", snap);
      audio.removeEventListener("pause", snap);
      audio.removeEventListener("seeked", snap);
    };
  }, [audioRef]);

  // rAF loop: line changes trigger React re-render; word highlighting is direct DOM manipulation
  useEffect(() => {
    if (!isActive) return;
    const loop = () => {
      const { ct, pt, playing } = audioSnapRef.current;
      // Subtracting looks at an earlier point in the song, which makes every line and every
      // word fire that much later. Applied here so line detection, word highlighting and
      // scrolling all shift together — there is no second place to keep in sync.
      const t = (playing ? ct + (performance.now() - pt) / 1000 : ct) - offsetRef.current;
      const lyr = lyricsDataRef.current;

      // Line detection — normal playback advances exactly one timestamp at a time. Seeked
      // events and clock discontinuities binary-search the parse-time timestamp array instead.
      // Plain lyrics have no timestamps, so they intentionally never get an active line.
      const timestamps = lyr?.timestamps || [];
      const timeDiscontinuity = t < prevTRef.current - 0.1 || t > prevTRef.current + 1;
      let newIdx = -1;
      if (lyr && syncedRef.current) {
        if (playbackJumpRef.current || timeDiscontinuity) {
          newIdx = findTimestampIndex(timestamps, t);
          playbackJumpRef.current = false;
        } else {
          newIdx = playbackLineIdxRef.current;
          if (timestamps[newIdx + 1] <= t) newIdx += 1;
        }
        playbackLineIdxRef.current = newIdx;
      }

      // Backward seek / restart (e.g. "previous" restarting the current song): time jumped
      // back >1s. videoId is unchanged so the song-change reset doesn't fire — handle it here.
      // Landing before the first line snaps to the top; landing on a line lets the centring
      // effect treat it as a jump (instant). A normal forward mid-song gap is unaffected.
      if (t < prevTRef.current - 1) {
        scrollStateRef.current.lastCenteredIdx = -1;
        if (newIdx < 0) {
          // Glide back to the top instead of a hard cut.
          scrollStateRef.current.target = 0;
          scrollStateRef.current.history = [];
          if (!fluidLyricsRef.current)
            containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
          // Fluid: leave scrollPos/velocity so the spring glides smoothly to the new target.
        }
      }
      prevTRef.current = t;

      // Gap detection: if gap between line's endTime and next line's start > 3s, deactivate at endTime
      let displayIdx = newIdx;
      if (newIdx >= 0 && lyr) {
        const line = lyr[newIdx];
        if (line.endTime != null) {
          const nextStart = lyr[newIdx + 1]?.time ?? Infinity;
          if (nextStart - line.endTime > 3 && t >= line.endTime) displayIdx = -1;
        }
      }

      if (displayIdx !== lastIdxRef.current) {
        // React does not own the frame-by-frame transform, so clear it explicitly before this
        // line is rendered as past/trailing content.
        if (sustainedWordRef.current) sustainedWordRef.current.style.transform = "";
        sustainedWordRef.current = null;
        const prevIdx = lastIdxRef.current;
        // If the previous line's endTime hasn't been reached yet, keep it visible as
        // a "trailing" line so it finishes naturally while the new line is already active.
        const newTrailing =
          prevIdx >= 0 && lyr?.[prevIdx]?.endTime != null && t < lyr[prevIdx].endTime
            ? prevIdx
            : -1;
        if (newTrailing !== trailingIdxRef.current) {
          trailingIdxRef.current = newTrailing;
          setTrailingIdx(newTrailing);
          // Reset trailing word tracking so the new trailing line gets a full repaint
          trailWordElsRef.current = [];
          activeTrailWordIdxRef.current = -1;
          activeTrailWordIdxRef.bgCurrent = -1;
        }
        lastIdxRef.current = displayIdx;
        setActiveIdx(displayIdx);
        activeWordIdxRef.current = -1;
        activeWordIdxRef.bgCurrent = -1;
        activeWordMaxRef.current = -1; // reset zoom dedupe for the new active line
        wordElsRef.current = []; // cleared until useLayoutEffect repopulates after render
        sustainedWordElsRef.current = [];
        bgContainerRef.current = null; // clear so RAF doesn't update the old line's element
      }

      // Expire trailing line once its endTime is reached
      if (trailingIdxRef.current >= 0) {
        const trailEnd = lyr?.[trailingIdxRef.current]?.endTime;
        if (trailEnd != null && t >= trailEnd) {
          trailingIdxRef.current = -1;
          setTrailingIdx(-1);
        }
      }

      // Gap indicator: true only when a line has played but we're between lines (gap > 3s)
      const isGap = newIdx >= 0 && displayIdx === -1;
      if (isGap !== inGapRef.current) {
        inGapRef.current = isGap;
        setInGap(isGap);
      }

      // Instrumental segment: no active line and the next vocal is still ≥ INSTR_LEAD away
      // (covers a long intro, mid-song breaks, and the outro). Synced lyrics only — plain
      // lyrics have time -1 and never resolve to displayIdx -1.
      const nextStart = timestamps[newIdx + 1] ?? Infinity;
      const inst = !!(displayIdx === -1 && lyr?.length && nextStart - t > 2);
      if (inst !== instVizRef.current) {
        instVizRef.current = inst;
        onInstChangeRef.current?.(inst);
      }

      // Word highlighting — direct DOM, bypasses React entirely.
      // ACTIVE line animates from newIdx. The TRAILING line (handed over before its
      // endTime) keeps animating in parallel so it finishes its syllable wipe instead
      // of snapping fully white. Both run through the same paintLineWords routine.
      const lyrLine = lyr?.[newIdx];
      // Zoom enabled only when the setting is on (pass null to disable per-syllable pop).
      const activeMainWordIdx = paintLineWords(
        lyrLine,
        wordElsRef.current,
        activeWordIdxRef,
        t,
        syllableZoomRef.current ? activeWordMaxRef : null,
        fluidLyricsRef.current
      );
      const activeWord = lyrLine?.renderTiming?.mainWords[activeMainWordIdx];
      const sustainedWordEl = sustainedWordElsRef.current[activeMainWordIdx] || null;
      if (sustainedWordRef.current && sustainedWordRef.current !== sustainedWordEl) {
        sustainedWordRef.current.style.transform = "";
      }
      sustainedWordRef.current = sustainedWordEl;
      if (sustainedWordEl) {
        sustainedWordEl.style.transform = `scale(${sustainedWordScale(lyrLine, activeWord, t).toFixed(4)})`;
      }
      if (trailingIdxRef.current >= 0) {
        // Trailing line: no zoom (null) — it only finishes its wipe quietly.
        paintLineWords(
          lyr?.[trailingIdxRef.current],
          trailWordElsRef.current,
          activeTrailWordIdxRef,
          t,
          null,
          fluidLyricsRef.current
        );
      }

      // BG vocals: fade in container independently based on bg-vocals' own start time
      if (bgContainerRef.current && lyrLine?.bgWords?.length) {
        const bgStart = lyrLine.renderTiming?.bgStartTime;
        if (bgStart != null) {
          const bgActive = t >= bgStart;
          bgContainerRef.current.style.opacity = bgActive ? "1" : "0.35";
        }
      }

      if (isPlaying) rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [audioRef, isActive, isPlaying]);

  // After React renders, cache word span elements and bg-vocals container for the active line
  useLayoutEffect(() => {
    const idx = activeIdx;
    if (idx >= 0) {
      // Scope to this instance's own container — Big Picture mounts a second LyricsOverlay while
      // the desktop one may still be in the DOM, and a global querySelector would grab the wrong
      // (earlier-in-document) instance's spans, leaving this instance's words unpainted.
      const root = containerRef.current || document;
      const lineEl = root.querySelector(`[data-lyric-idx="${idx}"]`);
      wordElsRef.current = lineEl ? Array.from(lineEl.querySelectorAll("[data-word-bright]")) : [];
      bgContainerRef.current = lineEl ? lineEl.querySelector("[data-bg-container]") : null;
      sustainedWordElsRef.current = lineEl
        ? Array.from(lineEl.querySelectorAll("[data-word-sustain]"))
        : [];
    } else {
      wordElsRef.current = [];
      bgContainerRef.current = null;
      sustainedWordElsRef.current = [];
      sustainedWordRef.current = null;
    }
    // Trailing line: cache its word spans and paint them immediately so already-sung
    // syllables stay bright (no 1-frame dim flash) while the line finishes its wipe.
    const tIdx = trailingIdxRef.current;
    if (tIdx >= 0) {
      const trailEl = (containerRef.current || document).querySelector(
        `[data-lyric-idx="${tIdx}"]`
      );
      trailWordElsRef.current = trailEl
        ? Array.from(trailEl.querySelectorAll("[data-word-bright]"))
        : [];
      activeTrailWordIdxRef.current = -1;
      activeTrailWordIdxRef.bgCurrent = -1;
      const { ct, pt, playing } = audioSnapRef.current;
      const tNow = (playing ? ct + (performance.now() - pt) / 1000 : ct) - offsetRef.current;
      paintLineWords(
        lyricsDataRef.current?.[tIdx],
        trailWordElsRef.current,
        activeTrailWordIdxRef,
        tNow,
        null,
        fluidLyricsRef.current
      );
    } else {
      trailWordElsRef.current = [];
    }
  }, [activeIdx, trailingIdx]);

  // Sync isCustomLyrics to parent
  useEffect(() => {
    onCustomLyricsStatusChange?.(isCustomLyrics);
  }, [isCustomLyrics]); // eslint-disable-line react-hooks/exhaustive-deps

  // Import lyrics: open file dialog, read content, POST to backend
  const importCustomLyrics = async () => {
    if (!track?.videoId) return;
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const path = await open({
        filters: [{ name: "Lyrics", extensions: ["lrc", "ttml"] }],
        title: "Lyrics importieren",
      });
      if (!path) return;
      const { readTextFile } = await import("@tauri-apps/plugin-fs");
      const content = await readTextFile(path);
      const fmt = path.toLowerCase().endsWith(".ttml") ? "ttml" : "lrc";
      const r = await fetch(`${API}/lyrics/custom`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ videoId: track.videoId, content, format: fmt }),
      });
      if (!r.ok) throw new Error("Speichern fehlgeschlagen");
      const parsed = fmt === "ttml" ? parseTtml(content) : parseLrc(content);
      setLyrics(parsed.length ? parsed : null);
      setSource("Custom");
      onSourceChange?.("Custom");
      setIsCustomLyrics(true);
      setLoading(false);
      onAddToast?.("Lyrics importiert", "success");
    } catch (e) {
      onAddToast?.("Import fehlgeschlagen", "error");
      console.error(e);
    }
  };

  // Remove custom lyrics
  const removeCustomLyrics = async () => {
    if (!track?.videoId) return;
    try {
      await fetch(`${API}/lyrics/custom/${track.videoId}`, { method: "DELETE" });
    } catch {
      /* intentionally ignored */
    }
    setIsCustomLyrics(false);
    setLyrics(null);
    setSource("");
    onSourceChange?.("");
    setLoading(true);
    // Trigger a fresh provider fetch by bumping a local key
    setCustomLyricsKey((k) => k + 1);
  };

  // Expose functions via refs for parent
  useEffect(() => {
    if (importLyricsRef) importLyricsRef.current = importCustomLyrics;
    if (removeCustomLyricsRef) removeCustomLyricsRef.current = removeCustomLyrics;
    if (openLyricsBrowserRef) openLyricsBrowserRef.current = () => setBrowserOpen(true);
  });

  useEffect(() => {
    if (!track) return;
    let cancelled = false;
    const abortController = new AbortController();

    const cacheKey = `kiyoshi-lyrics-${track.videoId}`;

    // Check for custom lyrics first
    fetch(`${API}/lyrics/custom/${track.videoId}`, { signal: abortController.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        if (data?.content) {
          const parsed = data.format === "ttml" ? parseTtml(data.content) : parseLrc(data.content);
          if (parsed.length) {
            setLyrics(parsed);
            setSource("Custom");
            onSourceChange?.("Custom");
            setIsCustomLyrics(true);
            setLoading(false);
            return;
          }
        }
        // No custom lyrics — proceed with normal fetch
        continueWithProviders();
      })
      .catch(() => {
        if (!cancelled) continueWithProviders();
      });

    function continueWithProviders() {
      // Forced provider: skip cache, fetch only that one provider
      if (forcedProvider) {
        const singleProviders = DEFAULT_LYRICS_PROVIDERS.map((p) => ({
          ...p,
          enabled: p.id === forcedProvider,
        }));
        fetchLyrics(
          track.title,
          track.artists,
          track.album,
          parseDurationToSeconds(track.duration),
          singleProviders,
          track.videoId || "",
          abortController.signal
        ).then((res) => {
          if (cancelled) return;
          if (res?.lrc) {
            setLyrics(res.lrc);
            setSource(res.source);
            setSubmitterName(res.submitterName || null);
            setAppliedVersionId(null);
            onSourceChange?.(res.source);
          } else {
            setLyrics(null);
            setSubmitterName(null);
            onSourceChange?.("");
            onProviderFailed?.(forcedProvider);
          }
          setLoading(false);
        });
        return;
      }

      // Check localStorage cache first (keyed by videoId), skip if refetching
      if (refetchKey === 0) {
        try {
          const cached = localStorage.getItem(cacheKey);
          if (cached) {
            const parsed = JSON.parse(cached);
            const { lrc, source, submitterName: cachedSubmitter } = parsed;
            // Invalidate old Unison cache entries that predate submitterName support
            if (source === "Unison" && !("submitterName" in parsed)) {
              localStorage.removeItem(cacheKey);
              throw new Error("stale");
            }
            setLyrics(lrc);
            setSource(source);
            setSubmitterName(cachedSubmitter || null);
            setAppliedVersionId(parsed.versionId ?? null);
            onSourceChange?.(source);
            setLoading(false);
            if (Array.isArray(parsed.failedIds)) {
              // Already have availability info — use immediately
              parsed.failedIds.forEach((id) => onProviderFailed?.(id));
            } else {
              // Old cache entry — check availability silently in background
              fetchLyrics(
                track.title,
                track.artists,
                track.album,
                parseDurationToSeconds(track.duration),
                providers,
                track.videoId || "",
                abortController.signal
              ).then((res) => {
                if (cancelled) return;
                const ids = res?.failedIds || [];
                ids.forEach((id) => onProviderFailed?.(id));
                try {
                  localStorage.setItem(
                    cacheKey,
                    JSON.stringify({
                      lrc,
                      source,
                      submitterName: cachedSubmitter || null,
                      failedIds: ids,
                    })
                  );
                } catch {
                  /* intentionally ignored */
                }
              });
            }
            return;
          }
        } catch {
          /* intentionally ignored */
        }
      } else {
        // Clear stale cache before refetching
        try {
          localStorage.removeItem(cacheKey);
        } catch {
          /* intentionally ignored */
        }
      }

      let shown = false;
      const applyBest = ({ best }) => {
        if (cancelled || shown || best === undefined) return;
        shown = true;
        if (best) {
          setLyrics(best.lrc);
          setSource(best.source);
          setSubmitterName(best.submitterName || null);
          setAppliedVersionId(null);
          onSourceChange?.(best.source);
        }
        setLoading(false);
      };

      fetchLyrics(
        track.title,
        track.artists,
        track.album,
        parseDurationToSeconds(track.duration),
        providers,
        track.videoId || "",
        abortController.signal,
        applyBest
      ).then((res) => {
        if (cancelled) return;
        if (res?.lrc) {
          if (!shown) {
            setLyrics(res.lrc);
            setSource(res.source);
            setSubmitterName(res.submitterName || null);
            setAppliedVersionId(null);
            onSourceChange?.(res.source);
          }
          try {
            localStorage.setItem(
              cacheKey,
              JSON.stringify({
                lrc: res.lrc,
                source: res.source,
                submitterName: res.submitterName || null,
                failedIds: res.failedIds || [],
              })
            );
          } catch {
            /* intentionally ignored */
          }
        }
        // Mark providers that were tried but failed
        res?.failedIds?.forEach((id) => onProviderFailed?.(id));
        setLoading(false);
      });
    } // end continueWithProviders
    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [track, refetchKey, forcedProvider, customLyricsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const lyricsSynced = !!(lyrics && lyrics.some((l) => (l.time ?? -1) >= 0));

  // Unique agents in order of first appearance (only when ≥2 distinct named agents)
  const lyricsAgents = useMemo(() => {
    if (!lyrics) return [];
    const seen = new Set();
    const result = [];
    for (const line of lyrics) {
      const key = line.agent?.id || line.agent?.name;
      if (key && line.agent.name && !seen.has(key)) {
        seen.add(key);
        result.push(line.agent);
      }
    }
    return result;
  }, [lyrics]);

  const activeAgent = lyrics?.[activeIdx]?.agent;

  // Centre the active line. Fluid mode drives scrollTop with a critically-damped spring
  // (SmoothDamp) — soft, no overshoot, and velocity-continuous so rapid line changes carry
  // their momentum (organic Apple-Music glide); otherwise the browser's native smooth scroll.
  // This state belongs entirely to the imperative scroll animation. Keeping it in one
  // private object makes that boundary explicit: React state owns the active line, while the
  // animator owns sub-frame position, velocity, and history.
  const scrollStateRef = useRef({
    target: 0,
    position: 0,
    velocity: 0,
    lastTime: 0,
    history: [],
    lastCenteredIdx: -1,
  });
  const activeIdxRef = useRef(activeIdx);
  useLayoutEffect(() => {
    activeIdxRef.current = activeIdx;
  }, [activeIdx]);

  useEffect(() => {
    if (userScrolling || activeIdx < 0 || !containerRef.current) return;
    const container = containerRef.current;
    let correctionFrame = 0;
    // Fluid wraps each line in a will-change:transform div (its own offsetParent), so the
    // inner [data-lyric] offsetTop is ~0 — measure the wrapper for positioning instead.
    const sel = fluidLyrics ? "[data-lyricdrift]" : "[data-lyric]";
    const bottomInset = fullscreen && playerBarVisible ? 104 : 0;
    const measure = () => {
      const activeEl = container.querySelectorAll(sel)[activeIdx];
      if (!activeEl) return null;
      return Math.max(
        0,
        activeEl.offsetTop - (container.clientHeight - bottomInset) / 2 + activeEl.clientHeight / 2
      );
    };
    const frame = requestAnimationFrame(() => {
      const target = measure();
      if (target == null) return;
      // A jump (song change, seek, or skipping >1 line) snaps instantly so it lands centred;
      // sequential line advances scroll smoothly. lastCenteredIdx is -1 right after a reset.
      const prev = scrollStateRef.current.lastCenteredIdx;
      const jump = prev < 0 || Math.abs(activeIdx - prev) > 1;
      scrollStateRef.current.lastCenteredIdx = activeIdx;
      if (!fluidLyrics) {
        container.scrollTo({ top: target, behavior: jump ? "auto" : "smooth" });
      } else {
        scrollStateRef.current.target = target;
        if (jump) {
          scrollStateRef.current.position = target;
          scrollStateRef.current.velocity = 0;
          container.scrollTop = target;
        }
      }
      // On a jump the new lyrics/line may still be settling (fonts, translations, wrapping) —
      // re-measure on the next frame and correct so it lands exactly centred.
      if (!jump) return;
      correctionFrame = requestAnimationFrame(() => {
        if (!containerRef.current || activeIdxRef.current !== activeIdx) return;
        const t2 = measure();
        if (t2 == null || Math.abs(t2 - target) < 1) return;
        if (!fluidLyrics) container.scrollTo({ top: t2, behavior: "auto" });
        else {
          scrollStateRef.current.target = t2;
          scrollStateRef.current.position = t2;
          scrollStateRef.current.velocity = 0;
          container.scrollTop = t2;
        }
      });
    });
    return () => {
      cancelAnimationFrame(frame);
      cancelAnimationFrame(correctionFrame);
    };
  }, [activeIdx, fluidLyrics, userScrolling]);

  useEffect(() => {
    userScrollingRef.current = false;
  }, [track?.videoId]);

  useEffect(() => {
    if (!fluidLyrics || !isActive || !isPlaying) return;
    const container = containerRef.current;
    if (!container) return;
    const wraps = container.querySelectorAll("[data-lyricdrift]");
    let raf = 0;
    let initializeFrame = 0;
    let previousDriftIdx = -1;
    const onUserScroll = () => {
      if (!userScrollingRef.current) {
        userScrollingRef.current = true;
        setUserScrollingTrackId(track?.videoId || null);
      }
      scrollStateRef.current.position = container.scrollTop;
      scrollStateRef.current.velocity = 0;
    };
    container.addEventListener("wheel", onUserScroll, { passive: true });
    container.addEventListener("touchmove", onUserScroll, { passive: true });

    // Spring from the Apple-Music video analysis: stiffness 120 / damping 20 / mass 1
    // (damping ratio ~0.91 → <1% overshoot, ~650ms settle). Velocity-continuous.
    const K = 120,
      C = 20,
      STAGGER = 0.05; // s of lag per line of distance (elastic chain)
    const histAt = (hist, t) => {
      if (hist.length === 0) return scrollStateRef.current.position;
      if (t <= hist[0].t) return hist[0].s;
      for (let i = hist.length - 1; i >= 0; i--) {
        if (hist[i].t <= t) {
          const a = hist[i],
            b = hist[i + 1] || a;
          return b.t === a.t ? a.s : a.s + (b.s - a.s) * ((t - a.t) / (b.t - a.t));
        }
      }
      return hist[hist.length - 1].s;
    };

    const tick = () => {
      raf = requestAnimationFrame(tick);
      const now = performance.now();
      const dt = Math.min((now - scrollStateRef.current.lastTime) / 1000, 0.04);
      scrollStateRef.current.lastTime = now;

      if (userScrollingRef.current) {
        scrollStateRef.current.position = container.scrollTop;
      } else {
        const target = scrollStateRef.current.target;
        let p = scrollStateRef.current.position,
          v = scrollStateRef.current.velocity;
        const steps = Math.max(1, Math.ceil(dt / 0.008)); // sub-step for stability
        const h = dt / steps;
        for (let s = 0; s < steps; s++) {
          v += (-K * (p - target) - C * v) * h;
          p += v * h;
        }
        if (Math.abs(p - target) < 0.15 && Math.abs(v) < 0.5) {
          p = target;
          v = 0;
        }
        scrollStateRef.current.position = p;
        scrollStateRef.current.velocity = v;
        container.scrollTop = p;
      }

      // Scroll-position history (for the staggered drift lookup).
      const hist = scrollStateRef.current.history;
      hist.push({ t: now, s: scrollStateRef.current.position });
      while (hist.length > 2 && hist[0].t < now - 600) hist.shift();

      // Staggered positional drift ("rubber-band" chain): only the active line and its six
      // neighbours on either side are visible enough to need per-frame updates. Clear the old
      // window when the active line changes so transforms never linger outside this 13-line
      // window.
      const ai = activeIdxRef.current;
      const cur = scrollStateRef.current.position;
      const clearWindow = (center) => {
        if (center < 0) return;
        const start = Math.max(0, center - FLUID_DRIFT_WINDOW);
        const end = Math.min(wraps.length - 1, center + FLUID_DRIFT_WINDOW);
        for (let n = start; n <= end; n++) {
          if (wraps[n]?.style.transform) wraps[n].style.transform = "";
        }
      };
      if (ai !== previousDriftIdx) {
        clearWindow(previousDriftIdx);
        previousDriftIdx = ai;
      }
      if (ai < 0) return;
      const start = Math.max(0, ai - FLUID_DRIFT_WINDOW);
      const end = Math.min(wraps.length - 1, ai + FLUID_DRIFT_WINDOW);
      for (let n = start; n <= end; n++) {
        const dist = Math.abs(n - ai);
        if (userScrollingRef.current || dist === 0) {
          if (wraps[n].style.transform) wraps[n].style.transform = "";
          continue;
        }
        const drift = Math.max(
          -34,
          Math.min(34, cur - histAt(hist, now - Math.min(dist, 8) * STAGGER * 1000))
        );
        wraps[n].style.transform = Math.abs(drift) > 0.1 ? `translateY(${drift.toFixed(2)}px)` : "";
      }
    };
    initializeFrame = requestAnimationFrame(() => {
      scrollStateRef.current.position = container.scrollTop;
      scrollStateRef.current.velocity = 0;
      scrollStateRef.current.lastTime = performance.now();
      scrollStateRef.current.history = [];
      raf = requestAnimationFrame(tick);
    });
    return () => {
      cancelAnimationFrame(initializeFrame);
      cancelAnimationFrame(raf);
      container.removeEventListener("wheel", onUserScroll);
      container.removeEventListener("touchmove", onUserScroll);
      wraps.forEach((w) => {
        w.style.transform = "";
      });
    };
  }, [fluidLyrics, isActive, isPlaying, lyrics]);

  useEffect(() => {
    if (fluidLyrics) return;
    const container = containerRef.current;
    if (!container) return;
    const onUserScroll = () => {
      if (!userScrollingRef.current) {
        userScrollingRef.current = true;
        setUserScrollingTrackId(track?.videoId || null);
      }
    };
    container.addEventListener("wheel", onUserScroll, { passive: true });
    container.addEventListener("touchmove", onUserScroll, { passive: true });
    return () => {
      container.removeEventListener("wheel", onUserScroll);
      container.removeEventListener("touchmove", onUserScroll);
    };
  }, [fluidLyrics, track?.videoId]);

  const resumeAutoscroll = useCallback(() => {
    userScrollingRef.current = false;
    setUserScrollingTrackId(null);
  }, []);

  return (
    <div
      onMouseMove={wakeScrollbar}
      onWheel={wakeScrollbar}
      onMouseLeave={sleepScrollbar}
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 50,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Fluid: a strong blurred + saturated album cover as the backdrop (Apple-style),
          replacing the ambient blobs. Darkened so the white lyrics stay high-contrast. */}
      {fluidLyrics && !ambientBackground && track?.thumbnail && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            zIndex: 0,
            pointerEvents: "none",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: "-12%",
              backgroundImage: `url(${thumb(track.thumbnail)})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              filter: "blur(90px) saturate(1.4) brightness(0.5)",
              transform: "scale(1.25)",
            }}
          />
        </div>
      )}
      {/* Ambient colour blobs — wrapped in an isolated layer so their mix-blend-mode
          stays contained and doesn't flatten the backdrop for the chips' backdrop-filter. */}
      {ambientVisualizer && isActive && !fluidLyrics && !ambientBackground && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            zIndex: 1,
            pointerEvents: "none",
            isolation: "isolate",
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: "-30%",
              pointerEvents: "none",
              background:
                "radial-gradient(ellipse 38% 30% at 44% 42%, var(--accent) 0%, transparent 70%)",
              mixBlendMode: "screen",
              animation: "blobDrift1 18s ease-in-out infinite",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: "-30%",
              pointerEvents: "none",
              background:
                "radial-gradient(ellipse 32% 38% at 63% 61%, #7b2ff7 0%, transparent 68%)",
              mixBlendMode: "screen",
              animation: "blobDrift2 23s ease-in-out infinite",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: "-30%",
              pointerEvents: "none",
              background:
                "radial-gradient(ellipse 44% 36% at 52% 46%, #1565c0 0%, transparent 65%)",
              mixBlendMode: "screen",
              animation: "blobDrift3 29s ease-in-out infinite",
            }}
          />
        </div>
      )}

      {/* Source badge — HeroUI Chip, glassy. Auto-hides with a slide-out like the
          scrollbar: revealed on cursor activity, slides off-right after idle. */}
      <div
        style={{
          position: "absolute",
          bottom: 12 + chipBottomLift,
          right: 16,
          zIndex: 2,
          display: "flex",
          alignItems: "center",
          gap: 6,
          transform: scrollActive ? "translateX(0)" : "translateX(calc(100% + 16px))",
          opacity: scrollActive ? 1 : 0,
          transition:
            "transform 0.42s cubic-bezier(0.4,0,0.2,1), opacity 0.32s ease, bottom 0.4s ease",
          pointerEvents: scrollActive ? "auto" : "none",
        }}
      >
        {source && (
          <button
            onClick={() => setBrowserOpen(true)}
            title={translate(language, "browseLyrics")}
            className="border-0 bg-transparent p-0 cursor-default"
          >
            <ChipRoot
              size="sm"
              className="border-0! px-3.5! py-1.5! transition-all duration-200 hover:brightness-125"
              style={{
                background: "rgba(255,255,255,0.1)",
                color: "rgba(255,255,255,0.9)",
                backdropFilter: "blur(18px)",
                WebkitBackdropFilter: "blur(18px)",
              }}
            >
              <ChipLabel
                className="font-semibold tracking-wide flex items-center gap-1.5"
                style={{ fontSize: "var(--t10)" }}
              >
                {source}
                {submitterName && <span style={{ opacity: 0.55 }}> · {submitterName}</span>}
                <CaretDown size={9} weight="bold" style={{ opacity: 0.6 }} />
              </ChipLabel>
            </ChipRoot>
          </button>
        )}
      </div>

      {browserOpen && (
        <LyricsBrowserModal
          track={track}
          providers={providers}
          currentSource={source}
          currentSubmitter={submitterName}
          currentVersionId={appliedVersionId}
          onApply={applyLyricsVersion}
          onOpenComposer={() => openComposer(track?.videoId)}
          onClose={() => setBrowserOpen(false)}
        />
      )}

      {/* Agent tags — bottom center, only when ≥2 named agents and toggle is on */}
      {showAgentTags && lyricsAgents.length >= 2 && (
        <div
          style={{
            position: "absolute",
            bottom: 14 + chipBottomLift,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 2,
            display: "flex",
            gap: 8,
            pointerEvents: "none",
            transition: "bottom 0.4s ease",
          }}
        >
          {lyricsAgents.map((agent) => {
            const key = agent.id || agent.name;
            const isActive = (activeAgent?.id || activeAgent?.name) === key;
            return (
              <ChipRoot
                key={key}
                size="sm"
                className="border-0! uppercase font-bold whitespace-nowrap px-3.5! py-1.5! transition-all duration-300"
                style={{
                  background: isActive
                    ? "color-mix(in srgb, var(--accent) 40%, transparent)"
                    : "rgba(255,255,255,0.08)",
                  color: isActive ? "#fff" : "rgba(255,255,255,0.5)",
                  backdropFilter: "blur(18px)",
                  WebkitBackdropFilter: "blur(18px)",
                  boxShadow: isActive
                    ? "0 2px 16px color-mix(in srgb, var(--accent) 32%, transparent)"
                    : "none",
                }}
              >
                <ChipLabel style={{ fontSize: 10, letterSpacing: "0.07em" }}>
                  {agent.name}
                </ChipLabel>
              </ChipRoot>
            );
          })}
        </div>
      )}

      {userScrolling && (
        <div
          className="animate-[pillRiseIn_0.26s_cubic-bezier(0.22,1,0.36,1)]"
          style={{
            position: "absolute",
            bottom: 64 + chipBottomLift,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 2,
            transition: "bottom 0.4s ease",
          }}
        >
          <div className="relative rounded-full shadow-[0_6px_22px_rgba(0,0,0,0.45)]">
            <div className="absolute inset-0 rounded-full bg-[rgba(255,255,255,0.13)] backdrop-blur-2xl" />
            <Button
              variant="ghost"
              size="sm"
              onPress={resumeAutoscroll}
              className="relative gap-2 h-9! px-4 rounded-full text-t13 font-semibold text-primary! border-none! bg-transparent! hover:bg-[rgba(255,255,255,0.09)]!"
            >
              <CaretDown size={13} weight="bold" />
              {t("resumeAutoscroll") || "Resume autoscroll"}
            </Button>
          </div>
        </div>
      )}

      {/* Lyrics */}
      <div
        ref={containerRef}
        className="lyrics-scroll"
        data-scroll-active={scrollActive ? "true" : "false"}
        style={{
          position: "relative",
          zIndex: 1,
          flex: 1,
          ...(lyrics
            ? {
                overflowY: "auto",
                padding: "40vh 80px 40vh",
                ...(fluidLyrics
                  ? {
                      maskImage:
                        "linear-gradient(to bottom, transparent 0, #000 110px, #000 calc(100% - 110px), transparent 100%)",
                      WebkitMaskImage:
                        "linear-gradient(to bottom, transparent 0, #000 110px, #000 calc(100% - 110px), transparent 100%)",
                    }
                  : {}),
              }
            : {
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                overflow: "hidden",
                padding: "0 80px",
              }),
        }}
      >
        {loading && (
          <div style={{ textAlign: "center", color: "var(--text-muted)" }}>
            {t("lyricsLoading")}
          </div>
        )}
        {!loading && !lyrics && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 16,
            }}
          >
            <div style={{ color: "rgba(255,255,255,0.75)", fontSize: "var(--t14)" }}>
              {t("noLyrics")}
            </div>
            <div style={{ color: "rgba(255,255,255,0.45)", fontSize: "var(--t12)" }}>
              {t("noLyricsHint")}
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              {/* Akari's LRC Maker */}
              <button
                onClick={() => openUrl("https://lrc-maker.github.io").catch(console.error)}
                style={{
                  background: "rgba(255,255,255,0.08)",
                  border: "none",
                  borderRadius: "var(--r-xl)",
                  padding: "8px 16px",
                  cursor: "default",
                  color: "#fff",
                  fontSize: "var(--t13)",
                  fontFamily: "var(--font)",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(255,255,255,0.16)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "rgba(255,255,255,0.08)";
                }}
              >
                <img src="/Akari's LRC Icon.svg" style={{ width: 26, height: 26 }} alt="" />
                {"Akari's LRC Maker"}
              </button>
              {/* Boidu's Composer — embedded in a Kodama window */}
              <button
                onClick={() => openComposer(track?.videoId).catch(console.error)}
                style={{
                  background: "rgba(255,255,255,0.08)",
                  border: "none",
                  borderRadius: "var(--r-xl)",
                  padding: "8px 16px",
                  cursor: "default",
                  color: "#fff",
                  fontSize: "var(--t13)",
                  fontFamily: "var(--font)",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(255,255,255,0.16)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "rgba(255,255,255,0.08)";
                }}
              >
                <img src="/Boidu Composer Icon.svg" style={{ width: 26, height: 26 }} alt="" />
                {"Boidu's Composer"}
              </button>
            </div>
            <button
              onClick={importCustomLyrics}
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "none",
                borderRadius: "var(--r-xl)",
                padding: "8px 20px",
                cursor: "default",
                color: "#fff",
                fontSize: "var(--t13)",
                fontFamily: "var(--font)",
                display: "flex",
                alignItems: "center",
                gap: 8,
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.12)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.06)";
              }}
            >
              <UploadSimple size={14} />
              {t("importLyrics")}
            </button>
          </div>
        )}
        {lyrics &&
          lyrics.map((line, i) => {
            const isActive = i === activeIdx;
            const isTrailing = i === trailingIdx; // previous line still playing while new one is active
            const isPast = i < activeIdx && !isTrailing;
            const isFuture = !isActive && !isTrailing && !isPast;

            const lineText = line.wordSync
              ? (line.words || []).map((w) => w.text).join("")
              : line.text || "\u00A0";

            // Trailing line looks identical to the active line — full opacity, no blur.
            // The existing CSS transition (0.4s) will carry it smoothly into the past
            // style once trailingIdx clears when endTime is reached.
            let blur, opacity;
            if (!lyricsSynced) {
              blur = 0;
              opacity = 0.9;
            } // plain lyrics: all readable, no active line
            else if (isActive || isTrailing) {
              blur = 0;
              opacity = 1;
            } else if (isPast) {
              blur = 3;
              opacity = 0.4;
            } else {
              blur = 0;
              opacity = 0.35;
            }
            // Fluid: upcoming (future) lines sit darker than already-sung ones.
            if (lyricsSynced && fluidLyrics && isFuture) opacity = 0.22;

            const seekable = line.time >= 0;
            const agentRole = line.agentRole; // "lead", "featured", "group", or null
            // Splitting a line into one inline-block per word takes it out of the bidi
            // algorithm, which only orders within a single text run — the boxes then sit in
            // DOM order, left to right, and Hebrew or Arabic comes out reversed the moment a
            // line goes active. dir on the wrapper (below) puts the boxes back into reading
            // order; textAlign here follows the same direction so the line reads from its
            // own starting edge.
            const lineRtl = isRtlText(lineText);
            // Line and translation each follow the direction of their own script: an RTL
            // text reads from the right, so its alignment mirrors. The agent role still
            // decides the baseline (featured right, group centred) — direction only flips it.
            const baseAlign =
              agentRole === "featured" ? "right" : agentRole === "group" ? "center" : "left";
            const mirrorAlign = (a) => (a === "left" ? "right" : a === "right" ? "left" : a);
            // Also feeds transformOrigin below, so the zoom grows away from the edge the
            // text is anchored to instead of pushing it out of the column.
            const textAlign = lineRtl ? mirrorAlign(baseAlign) : baseAlign;
            const trAlign = isRtlLang(translationLang) ? mirrorAlign(baseAlign) : baseAlign;
            const zoomPull =
              fluidLyrics && (isActive || isTrailing)
                ? `${((1 - 1 / LYRIC_ZOOM) * 100).toFixed(2)}%`
                : undefined;
            // Trailing spaces in the word list would sit at the right edge and push a
            // right-aligned active line visually left. Drop them so it stays flush-right.
            let renderWords = line.words || [];
            {
              let n = renderWords.length;
              while (n > 0 && renderWords[n - 1].isSpace) n--;
              renderWords = renderWords.slice(0, n);
            }
            const lineNode = (
              <div
                key={i}
                data-lyric="true"
                data-lyric-idx={i}
                onClick={
                  seekable
                    ? () => {
                        audioRef.current.currentTime = Math.max(0, line.time + offsetRef.current);
                      }
                    : undefined
                }
                onMouseEnter={
                  seekable
                    ? (e) => {
                        e.currentTarget.style.opacity = Math.min(1, opacity + 0.25);
                      }
                    : undefined
                }
                onMouseLeave={
                  seekable
                    ? (e) => {
                        e.currentTarget.style.opacity = opacity;
                      }
                    : undefined
                }
                style={{
                  fontSize: fontSize,
                  fontWeight: 700,
                  lineHeight: 1.5,
                  marginBottom: 24,
                  cursor: "default",
                  filter: `blur(${blur}px)`,
                  opacity,
                  transform: fluidLyrics
                    ? `scale(${isActive || isTrailing ? 1.06 : 1})`
                    : undefined,
                  transformOrigin:
                    textAlign === "right"
                      ? "right center"
                      : textAlign === "center"
                        ? "center center"
                        : "left center",
                  transition: fluidLyrics
                    ? "transform 0.25s ease-out, opacity 0.4s ease-out, filter 0.4s ease-out"
                    : "filter 0.4s ease, opacity 0.4s ease",
                  userSelect: "none",
                  borderRadius: "var(--r-lg)",
                  padding: "2px 8px",
                  margin: "0 -8px 24px",
                  textAlign,
                }}
              >
                <div>
                  {(isActive || isTrailing) && line.wordSync ? (
                    <span style={{ whiteSpace: "pre-wrap" }}>
                      {renderWords.map((word, wi) =>
                        word.isSpace ? (
                          <span key={wi}>{word.text}</span>
                        ) : (
                          <span
                            key={wi}
                            data-word-sustain="true"
                            style={{ display: "inline-block", transformOrigin: "center center" }}
                          >
                            <span style={{ position: "relative", display: "inline-block" }}>
                              <span style={{ color: "rgba(255,255,255,0.25)" }}>{word.text}</span>
                              <span
                                data-word-bright="true"
                                style={{
                                  position: "absolute",
                                  top: 0,
                                  left: 0,
                                  right: 0,
                                  bottom: 0,
                                  color: "white",
                                  opacity: 0,
                                  WebkitMaskImage:
                                    "linear-gradient(to right, black -6px, transparent 6px)",
                                  maskImage:
                                    "linear-gradient(to right, black -6px, transparent 6px)",
                                  pointerEvents: "none",
                                }}
                              >
                                {word.text}
                              </span>
                            </span>
                          </span>
                        )
                      )}
                    </span>
                  ) : (
                    <span style={{ color: "#fff" }}>{lineText}</span>
                  )}
                  {/* Background vocals — rendered in smaller text below the main line.
                  Initial opacity when isActive: 0.35 (dim). RAF loop sets it to 1
                  only when t >= bgWords[0].time so it activates independently. */}
                  {line.bgWords?.length > 0 && (
                    <div
                      data-bg-container="true"
                      style={{
                        fontSize: "0.68em",
                        fontWeight: 600,
                        marginTop: 3,
                        lineHeight: 1.4,
                        opacity: isActive ? 0.35 : 0.9,
                        transition: "opacity 0.3s ease",
                      }}
                    >
                      {isActive || isTrailing ? (
                        <span style={{ whiteSpace: "pre-wrap" }}>
                          {line.bgWords.map((word, wi) =>
                            word.isSpace ? (
                              <span key={wi}>{word.text}</span>
                            ) : (
                              <span
                                key={wi}
                                style={{ position: "relative", display: "inline-block" }}
                              >
                                <span style={{ color: "rgba(255,255,255,0.25)" }}>{word.text}</span>
                                <span
                                  data-word-bright="true"
                                  style={{
                                    position: "absolute",
                                    top: 0,
                                    left: 0,
                                    right: 0,
                                    bottom: 0,
                                    color: "white",
                                    opacity: 0,
                                    WebkitMaskImage:
                                      "linear-gradient(to right, black -6px, transparent 6px)",
                                    maskImage:
                                      "linear-gradient(to right, black -6px, transparent 6px)",
                                    pointerEvents: "none",
                                  }}
                                >
                                  {word.text}
                                </span>
                              </span>
                            )
                          )}
                        </span>
                      ) : (
                        <span style={{ color: "rgba(255,255,255,0.55)" }}>
                          {line.bgWords.map((w) => w.text).join("")}
                        </span>
                      )}
                    </div>
                  )}
                  {line.bgText && (
                    <div
                      style={{
                        fontSize: "0.68em",
                        fontWeight: 600,
                        marginTop: 3,
                        lineHeight: 1.4,
                        opacity: isActive ? 0.35 : 0.9,
                        color: "#fff",
                      }}
                    >
                      {line.bgText}
                    </div>
                  )}
                </div>
                {showRomaji && romajiLines?.[i] && (
                  <div
                    style={{
                      fontSize: romajiFontSize,
                      fontWeight: 500,
                      color: "rgba(255,255,255,0.55)",
                      opacity: isActive ? 1 : 0.6,
                      marginTop: 4,
                      lineHeight: 1.4,
                      textAlign,
                    }}
                  >
                    {romajiLines[i]}
                  </div>
                )}
                {showTranslation && translations?.[i] && translations[i] !== lineText && (
                  <div
                    style={{
                      fontSize: translationFontSize,
                      fontWeight: 600,
                      color: "var(--accent)",
                      opacity: isActive ? 0.9 : 0.45,
                      marginTop: 6,
                      lineHeight: 1.4,
                      textAlign,
                    }}
                  >
                    {translations[i]}
                  </div>
                )}
              </div>
            );
            // Fluid mode wraps each line so the rAF scroll loop can drive a per-line
            // positional drift (translateY) on the wrapper while the line's own scale stays
            // a CSS transition on the inner node (separate elements → no transform clash).
            return fluidLyrics ? (
              <div key={i} data-lyricdrift="true" style={{ willChange: "transform" }}>
                {lineNode}
              </div>
            ) : (
              lineNode
            );
          })}
      </div>
    </div>
  );
}
