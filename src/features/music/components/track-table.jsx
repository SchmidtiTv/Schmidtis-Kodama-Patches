import { useState, useEffect, useMemo, useRef, useLayoutEffect } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Button } from "@heroui/react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { API } from "@/shared/api/client.js";
import { thumb, hiResThumb } from "@/shared/api/thumbnails.js";
import { RetryingImage } from "@/shared/ui/retrying-image.jsx";
import { AmbientBackdrop } from "@/shared/ui/ambient-backdrop.jsx";
import { useAnimations, useTrackNumbers } from "@/features/settings/display-context.jsx";
import { useLang } from "@/shared/i18n/context.jsx";
import { useAccentColor } from "@/features/music/hooks/use-accent-color.js";
import {
  collectTrackVersions,
  isLikelyVideo,
  videoEvidenceForTrack,
} from "@/features/music/track-deduplication.js";
import { Tooltip } from "@/shared/ui/tooltip.jsx";
import { ExplicitBadge, ArtistLinks, SkeletonRow } from "@/features/music/components/rows.jsx";
import { parseDurationToSeconds } from "@/features/lyrics/parse.js";
import { buildMixTrackOrder } from "@/features/music/mix-track-order.js";
import { resolveMixCollectionId } from "@/features/music/mix-collection.js";
import { usePlaybackStatus, usePlayerActions } from "@/features/player/player-context.jsx";
import { useDownloadState, useDownloadActions } from "@/features/downloads/download-context.jsx";
import {
  ArrowClockwise,
  ArrowLeft,
  CheckCircle,
  Clock,
  ClockCounterClockwise,
  Crown,
  DownloadSimple,
  DotsThreeVertical,
  Heart,
  MagnifyingGlass,
  MusicNote,
  Pause,
  Play,
  Queue,
  Shuffle,
  Sort,
  SortDown,
  SortUp,
  Tag,
  Trash,
  VinylRecord,
} from "@/shared/icons/icons.jsx";

function formatTotalDuration(tracks) {
  const totalSecs = tracks.reduce((sum, t) => sum + (parseDurationToSeconds(t.duration) || 0), 0);
  if (totalSecs <= 0) return null;
  const h = Math.floor(totalSecs / 3600);
  const m = Math.floor((totalSecs % 3600) / 60);
  const s = totalSecs % 60;
  if (h > 0) return `${h} h ${m} min`;
  if (m > 0) return `${m} min ${s} s`;
  return `${s} s`;
}

function findScrollParent(element) {
  for (let parent = element.parentElement; parent; parent = parent.parentElement) {
    const overflowY = getComputedStyle(parent).overflowY;
    if (
      (overflowY === "auto" || overflowY === "scroll") &&
      parent.scrollHeight > parent.clientHeight
    ) {
      return parent;
    }
  }
  return null;
}

function tableGridColumns({ hasSelection, showAlbumColumn, showBpmColumn, showKeyColumn }) {
  const selectionColumn = hasSelection ? "28px " : "";
  const mixColumns = `${showBpmColumn ? "58px " : ""}${showKeyColumn ? "62px " : ""}`;
  const albumColumn = showAlbumColumn ? "minmax(0,1fr) " : "";
  return `${selectionColumn}36px minmax(0,2.2fr) ${mixColumns}${albumColumn}28px 52px`;
}

export function SelActionBtn({ icon, label, onClick, danger, iconOnly, horizontal }) {
  const btn = (
    <Button
      variant="ghost"
      size="sm"
      isIconOnly={iconOnly}
      onPress={onClick}
      className={`rounded-xl shrink-0 ${
        danger
          ? "text-[var(--status-danger)]! hover:text-white! hover:bg-[rgba(239,68,68,0.85)]!"
          : ""
      } ${horizontal ? "gap-2 px-4.5!" : ""}`}
    >
      {icon}
      {!iconOnly && <span className="text-t13 font-medium whitespace-nowrap">{label}</span>}
    </Button>
  );
  return iconOnly ? <Tooltip text={label}>{btn}</Tooltip> : btn;
}

export function TableRow({
  track,
  index,
  isPlaying,
  onPlay,
  onOpenArtist,
  onOpenAlbum,
  showAlbumColumn,
  onContextMenu,
  isCached,
  isDownloading,
  onDownload,
  isPremiumOnly,
  selected = false,
  onToggleSelect,
  mixAnalysis,
  showBpmColumn = false,
  showKeyColumn = false,
}) {
  const anim = useAnimations();
  const t = useLang();
  const showNum = useTrackNumbers();

  const gridCols = tableGridColumns({
    hasSelection: Boolean(onToggleSelect),
    showAlbumColumn,
    showBpmColumn,
    showKeyColumn,
  });

  const row = (
    <div
      data-track-id={track.videoId}
      onClick={isPremiumOnly ? undefined : () => onPlay(track)}
      onContextMenu={
        !isPremiumOnly && onContextMenu
          ? (e) => {
              e.preventDefault();
              onContextMenu(e, track);
            }
          : undefined
      }
      style={{ gridTemplateColumns: gridCols }}
      className={`group grid items-center gap-3 px-4 py-2 min-h-[68px] rounded-lg cursor-default transition-colors ${
        selected
          ? "bg-[color-mix(in_srgb,var(--accent)_10%,transparent)]"
          : isPlaying
            ? "bg-[color-mix(in_srgb,var(--accent)_8%,transparent)]"
            : "hover:bg-hover"
      } ${isPremiumOnly ? "opacity-40" : ""}`}
    >
      {onToggleSelect && (
        <div
          onClick={(e) => {
            e.stopPropagation();
            onToggleSelect();
          }}
          className={`flex items-center justify-center shrink-0 cursor-default transition-opacity ${selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
        >
          {selected ? (
            <CheckCircle size={18} weight="fill" className="text-accent" />
          ) : (
            <div className="w-4 h-4 rounded-full border-[1.5px] border-[var(--text-muted)] bg-elevated" />
          )}
        </div>
      )}
      <div
        className={`text-center text-t12 tabular-nums ${isPlaying ? "text-accent" : "text-muted"}`}
        aria-hidden={!showNum}
      >
        {showNum ? index + 1 : ""}
      </div>

      {/* Title and artist form one compact, scan-friendly identity column. */}
      <div className="flex min-w-0 items-center gap-3 overflow-hidden">
        <div className="relative w-12 h-12 shrink-0 overflow-hidden rounded-md bg-elevated">
          {track.thumbnail ? (
            <RetryingImage
              src={thumb(hiResThumb(track.thumbnail, 120))}
              alt=""
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full bg-[var(--placeholder-gradient)]" />
          )}
          {isPlaying && (
            <div className="absolute inset-0 flex items-center justify-center gap-0.5 bg-black/50">
              {anim ? (
                [1, 2, 3].map((b) => (
                  <div
                    key={b}
                    className="w-[3px] rounded-[2px] bg-accent"
                    style={{
                      animation: `eqBar${b} ${0.6 + b * 0.15}s ease-in-out infinite`,
                      animationDelay: `${b * 0.1}s`,
                    }}
                  />
                ))
              ) : (
                <Pause size={12} className="text-accent" />
              )}
            </div>
          )}
          {!isPlaying && !isPremiumOnly && (
            <div className="absolute inset-0 hidden items-center justify-center bg-black/45 text-white group-hover:flex">
              <Play size={17} weight="fill" />
            </div>
          )}
        </div>
        <div className="min-w-0">
          <div
            className={`flex items-center gap-1 overflow-hidden text-t14 font-medium ${isPlaying ? "text-accent" : "text-primary"}`}
          >
            <span className="truncate min-w-0">{track.title}</span>
            {track.isExplicit && <ExplicitBadge />}
          </div>
          <div className="text-t12 text-secondary mt-0.5 truncate">
            <ArtistLinks track={track} onOpenArtist={onOpenArtist} />
            {(!track.artists || (Array.isArray(track.artists) && track.artists.length === 0)) &&
              "—"}
          </div>
        </div>
      </div>
      {showBpmColumn && (
        <div className="text-t12 text-secondary text-center tabular-nums truncate">
          {mixAnalysis?.status === "complete" ? mixAnalysis.bpm : mixAnalysis ? "…" : "—"}
        </div>
      )}
      {showKeyColumn && (
        <div className="text-t12 text-secondary text-center truncate">
          {mixAnalysis?.status === "complete" ? mixAnalysis.camelotKey : "—"}
        </div>
      )}
      {/* Album */}
      {showAlbumColumn && (
        <div
          onClick={(e) => {
            if (track.albumBrowseId && onOpenAlbum) {
              e.stopPropagation();
              onOpenAlbum({ browseId: track.albumBrowseId, title: track.album });
            }
          }}
          className="text-t12 text-secondary truncate cursor-default transition-colors hover:text-primary"
        >
          {track.album || "—"}
        </div>
      )}
      {/* Download */}
      <div
        className="flex justify-center"
        onClick={(e) => {
          e.stopPropagation();
          if (!isPremiumOnly && onDownload && !isCached && !isDownloading) onDownload(track);
        }}
      >
        {isPremiumOnly ? (
          <Crown size={14} weight="fill" className="text-[var(--status-warning)]" />
        ) : isCached ? (
          <CheckCircle size={14} className="text-[var(--status-success)]" />
        ) : isDownloading ? (
          <DownloadSimple size={14} className="text-accent animate-pulse" />
        ) : onDownload ? (
          <DownloadSimple
            size={14}
            className="text-muted cursor-default opacity-0 transition-opacity group-hover:opacity-100"
          />
        ) : null}
      </div>
      {/* Duration */}
      <div className="text-t12 text-muted text-right">{track.duration || "—"}</div>
    </div>
  );

  return isPremiumOnly ? <Tooltip text={t("premiumOnly")}>{row}</Tooltip> : row;
}

export function PlaylistLayout({
  title,
  description,
  thumbnail,
  playlistId,
  mixCollectionId,
  tracks,
  total,
  loading,
  progress,
  cached,
  onBack,
  isLiked,
  onOpenArtist,
  onOpenAlbum,
  isAlbum,
  albumArtists,
  albumArtistBrowseId,
  browseId,
  year,
  musicbrainzDetails,
  onRefresh,
  onTrackContextMenu,
  onDownloadAll,
  onRemoveAll,
  hideExplicit,
  selectedTracks,
  onToggleSelect,
  onSelectAll,
  extraActions,
  typeLabel,
  hasMore = false,
  loadingMore = false,
  onLoadMore,
  onCollectionActions,
}) {
  const { track: currentTrack, isPlaying } = usePlaybackStatus();
  const { handlePlay, enqueue } = usePlayerActions();
  // Cached/downloading/premium id sets + the single-track download action come from
  // DownloadContext; onDownloadAll/onRemoveAll stay props since only collection/album
  // views offer a "download all" action.
  const { cachedSongIds, downloadingIds, premiumSongIds } = useDownloadState();
  const { downloadSong: onDownloadSong } = useDownloadActions();
  const accentColor = useAccentColor(thumbnail);
  const t = useLang();
  const showNum = useTrackNumbers();
  const [trackSearch, setTrackSearch] = useState("");
  const [searchVisible, setSearchVisible] = useState(false);
  const searchInputRef = useRef(null);
  const loggedVideoIdsRef = useRef(new Set());
  const [sort, setSort] = useState({ key: null, dir: "asc" });
  const [mixEnabled, setMixEnabled] = useState(false);
  const [mixLoading, setMixLoading] = useState(false);
  const [mixConfig, setMixConfig] = useState(null);
  const collectedTracks = useMemo(() => collectTrackVersions(tracks), [tracks]);
  const resolvedMixCollectionId = useMemo(
    () => resolveMixCollectionId({ playlistId, isAlbum, mixCollectionId }),
    [isAlbum, mixCollectionId, playlistId]
  );
  // What the player should remember this queue "came from". Mix-collection playlists/albums take
  // priority (their origin drives mix-transition polling in player.jsx); a plain album play still
  // records enough to show "Playing from X — track N of M" in the player and queue panel. The
  // track id list is captured now, not read live off the queue later, so that info survives a
  // later shuffle.
  const playOrigin = useMemo(() => {
    if (resolvedMixCollectionId) {
      return { kind: "mixCollection", mixCollectionId: resolvedMixCollectionId };
    }
    if (isAlbum && browseId) {
      return {
        kind: "album",
        title,
        thumbnail,
        browseId,
        trackIds: tracks.map((track) => track.videoId).filter(Boolean),
      };
    }
    return null;
  }, [resolvedMixCollectionId, isAlbum, browseId, title, thumbnail, tracks]);
  const mixTrackOrder = useMemo(() => buildMixTrackOrder(tracks), [tracks]);
  const analysisJobRef = useRef(null);

  useEffect(() => {
    if (!resolvedMixCollectionId) {
      setMixEnabled(false);
      return;
    }
    let cancelled = false;
    setMixLoading(true);
    fetch(`${API}/playlist/${encodeURIComponent(resolvedMixCollectionId)}/mix`)
      .then((response) => (response.ok ? response.json() : { enabled: false }))
      .then((config) => {
        if (!cancelled) {
          setMixConfig(config);
          setMixEnabled(config.enabled === true);
        }
      })
      .catch(() => {
        if (!cancelled) setMixEnabled(false);
      })
      .finally(() => {
        if (!cancelled) setMixLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [resolvedMixCollectionId]);

  const toggleMix = async () => {
    if (!resolvedMixCollectionId || mixLoading) return;
    const enabled = !mixEnabled;
    setMixLoading(true);
    try {
      const response = await fetch(
        `${API}/playlist/${encodeURIComponent(resolvedMixCollectionId)}/mix`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        }
      );
      if (response.ok) {
        const config = await response.json();
        setMixConfig(config);
        setMixEnabled(config.enabled === true);
      }
    } finally {
      setMixLoading(false);
    }
  };

  useEffect(() => {
    if (!resolvedMixCollectionId || !mixEnabled || loading || !mixTrackOrder.length) return;
    const signature = mixTrackOrder
      .map(({ instanceId, videoId }) => `${instanceId}:${videoId}`)
      .join("|");
    if (analysisJobRef.current?.signature === signature) return;
    let cancelled = false;
    let timeoutId;
    const poll = async (jobId) => {
      try {
        const response = await fetch(
          `${API}/playlist/${encodeURIComponent(resolvedMixCollectionId)}/mix/analysis/${jobId}`
        );
        if (!response.ok || cancelled) return;
        const job = await response.json();
        setMixConfig((config) => ({ ...config, trackAnalysis: job.tracks || {} }));
        if (!["complete", "cancelled", "failed"].includes(job.status)) {
          timeoutId = window.setTimeout(() => poll(jobId), 800);
        }
      } catch {
        // Analysis failures never interrupt ordinary playlist playback.
      }
    };
    const start = async () => {
      try {
        await fetch(`${API}/playlist/${encodeURIComponent(resolvedMixCollectionId)}/mix`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ trackOrder: mixTrackOrder }),
        });
        const response = await fetch(
          `${API}/playlist/${encodeURIComponent(resolvedMixCollectionId)}/mix/analysis`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tracks: mixTrackOrder }),
          }
        );
        if (!response.ok || cancelled) return;
        const job = await response.json();
        analysisJobRef.current = { signature, jobId: job.jobId };
        poll(job.jobId);
      } catch {
        // Analysis is an enhancement, so network errors remain silent here.
      }
    };
    start();
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [loading, mixEnabled, mixTrackOrder, resolvedMixCollectionId]);

  useEffect(() => {
    tracks.filter(isLikelyVideo).forEach((track) => {
      const logKey = track.videoId || `${track.title}:${track.artists}`;
      if (loggedVideoIdsRef.current.has(logKey)) return;
      loggedVideoIdsRef.current.add(logKey);
      console.warn("[Kodama] Video variant detected", {
        videoId: track.videoId,
        title: track.title,
        artists: track.artists,
        album: track.album,
        evidence: videoEvidenceForTrack(track),
        rawVideoType: track.videoType || "missing",
        thumbnailDimensions: track.thumbnailDimensions || ["unknown"],
      });
    });
  }, [tracks]);

  useEffect(() => {
    if (searchVisible) searchInputRef.current?.focus();
  }, [searchVisible]);

  useEffect(() => setSort({ key: null, dir: "asc" }), [title]);

  const collator = useMemo(() => {
    try {
      return new Intl.Collator(localStorage.getItem("kiyoshi-lang") || undefined, {
        sensitivity: "base",
        numeric: true,
      });
    } catch {
      return new Intl.Collator(undefined, { sensitivity: "base", numeric: true });
    }
  }, []);

  const visibleTracks = useMemo(() => {
    const query = trackSearch.trim().toLowerCase();
    const filtered = collectedTracks.filter((track) => {
      if (hideExplicit && track.isExplicit) return false;
      return (
        !query ||
        (track.title || "").toLowerCase().includes(query) ||
        (track.artists || "").toLowerCase().includes(query)
      );
    });
    if (!sort.key) return filtered;

    const direction = sort.dir === "asc" ? 1 : -1;
    const valueFor = (track) => {
      const value = track[sort.key];
      return Array.isArray(value)
        ? value
            .map((artist) => artist?.name || artist)
            .filter(Boolean)
            .join(", ")
        : String(value || "");
    };
    return [...filtered].sort((left, right) => {
      if (sort.key === "duration") {
        return (
          ((parseDurationToSeconds(left.duration) || 0) -
            (parseDurationToSeconds(right.duration) || 0)) *
          direction
        );
      }
      return collator.compare(valueFor(left), valueFor(right)) * direction;
    });
  }, [collectedTracks, collator, hideExplicit, sort, trackSearch]);

  const sortableHead = (key, label, align = "left", tooltip = null) => {
    const active = sort.key === key;
    const header = (
      <div
        className="group flex min-w-0 items-center gap-1.5 overflow-hidden cursor-default select-none transition-colors"
        style={{
          justifyContent:
            align === "right" ? "flex-end" : align === "center" ? "center" : "flex-start",
          color: active ? "var(--accent)" : undefined,
        }}
        onClick={() =>
          setSort((current) =>
            current.key !== key
              ? { key, dir: "asc" }
              : current.dir === "asc"
                ? { key, dir: "desc" }
                : { key: null, dir: "asc" }
          )
        }
      >
        <span className="flex min-w-0 items-center truncate">{label}</span>
        {active ? (
          sort.dir === "asc" ? (
            <SortUp size={11} />
          ) : (
            <SortDown size={11} />
          )
        ) : (
          <Sort size={11} className="opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
      </div>
    );
    return tooltip ? <Tooltip text={tooltip}>{header}</Tooltip> : header;
  };

  const totalDuration = formatTotalDuration(tracks);
  const skeletonCount = hasMore ? 0 : total ? Math.max(0, total - tracks.length) : 0;

  // ── List virtualization ─────────────────────────────────────────────────────
  // Only the visible rows are mounted (constant DOM regardless of list length).
  // The whole page scrolls (the list is NOT the scroll container), so we virtualize
  // against the nearest scrolling ancestor and offset by the list's position in it.
  const listInnerRef = useRef(null);
  const tableHeaderRef = useRef(null);
  const [scrollEl, setScrollEl] = useState(null);
  const [listScrollMargin, setListScrollMargin] = useState(0);
  const [measureTick, bumpMeasure] = useState(0);
  const [tableWidth, setTableWidth] = useState(Number.POSITIVE_INFINITY);

  useLayoutEffect(() => {
    const header = tableHeaderRef.current;
    if (!header) return;
    const updateWidth = () => setTableWidth(header.clientWidth);
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(header);
    return () => observer.disconnect();
  }, []);

  // Narrow panes preserve the identity column by dropping secondary metadata in priority order.
  const showAlbumColumn = !isAlbum && tableWidth >= 620;
  const showKeyColumn = mixEnabled && tableWidth >= 500;
  const showBpmColumn = mixEnabled && tableWidth >= 420;

  useEffect(() => {
    const onResize = () => bumpMeasure((n) => n + 1);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Re-measures the list's offset inside the scroll container. This used to run after every
  // render with no dependency list, and it sets state — so each pass could schedule another,
  // which React reports as a "nested-update" commit, plus two forced-layout getBoundingClientRect
  // calls per pass.
  //
  // The offset only moves when the header's height changes — which happens as the track count
  // and metadata stream in, or the header wraps to a different width — or on resize, so those
  // are the dependencies. Scrolling does not change it, and scrolling was what made this run
  // dozens of times a second.
  useLayoutEffect(() => {
    const inner = listInnerRef.current;
    if (!inner) return;
    const sc =
      scrollEl?.isConnected && scrollEl.contains(inner) ? scrollEl : findScrollParent(inner);
    if (sc !== scrollEl) setScrollEl(sc);
    if (!sc) return;
    const top = Math.max(
      0,
      Math.round(inner.getBoundingClientRect().top - sc.getBoundingClientRect().top + sc.scrollTop)
    );
    setListScrollMargin((prev) => (prev === top ? prev : top));
  }, [scrollEl, tracks.length, total, title, tableWidth, measureTick]);

  const skelN = trackSearch ? 0 : skeletonCount;
  const rowCount = visibleTracks.length + skelN;
  const rowVirtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => scrollEl,
    estimateSize: () => 68,
    overscan: 12,
    scrollMargin: listScrollMargin,
  });

  useEffect(() => {
    if (!scrollEl || !hasMore || loadingMore || !onLoadMore) return;
    let requested = false;
    const loadWhenNearEnd = () => {
      const list = listInnerRef.current;
      if (!list || requested) return;
      const distanceToEnd =
        list.getBoundingClientRect().bottom - scrollEl.getBoundingClientRect().bottom;
      if (distanceToEnd > 400) return;
      requested = true;
      onLoadMore();
    };
    scrollEl.addEventListener("scroll", loadWhenNearEnd, { passive: true });
    loadWhenNearEnd();
    return () => scrollEl.removeEventListener("scroll", loadWhenNearEnd);
  }, [hasMore, loadingMore, onLoadMore, scrollEl, tracks.length]);

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100%" }}>
      <style>{`
        @keyframes pulse{0%,100%{opacity:.4}50%{opacity:.9}}
        .playlist-hero-container { container-type: inline-size; }
        @container (max-width: 560px) {
          .playlist-hero-cover { width: 112px !important; height: 112px !important; }
          .playlist-hero-title { font-size: 30px !important; }
        }
        @container (max-width: 420px) {
          .playlist-hero-content { flex-direction: column; gap: 16px !important; }
          .playlist-hero-details { width: 100%; }
          .playlist-hero-cover { width: 120px !important; height: 120px !important; }
          .playlist-action-controls { gap: 8px !important; }
          .playlist-primary-actions { gap: 8px !important; }
          .playlist-secondary-actions { gap: 6px !important; }
          .playlist-play-action { padding: 0 16px !important; }
          .playlist-shuffle-action { padding: 0 12px !important; }
          .playlist-mix-action { padding: 0 9px !important; }
        }
      `}</style>

      {/* Hero header */}
      <div
        style={{
          position: "relative",
        }}
      >
        {/* Blurred, crossfading cover backdrop — album pages only, playlists/history/liked keep
            their flat background. */}
        {isAlbum && thumbnail && <AmbientBackdrop thumbnail={thumbnail} />}

        {/* Keep the shared hero offset even when this top-level view has no back action. */}
        <div style={{ padding: "48px 22px 18px", display: "flex", gap: 8 }}>
          {onBack && (
            <button
              onClick={onBack}
              style={{
                width: 36,
                height: 36,
                borderRadius: "50%",
                background: "rgba(0,0,0,0.38)",
                border: "0.5px solid rgba(255,255,255,0.12)",
                color: "rgba(255,255,255,0.9)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "default",
                backdropFilter: "blur(8px)",
                transition: "background 0.15s",
                padding: 0,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(0,0,0,0.58)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(0,0,0,0.38)")}
            >
              <ArrowLeft size={16} />
            </button>
          )}
        </div>

        {/* Album / playlist info */}
        <div className="playlist-hero-container">
          <div
            className="playlist-hero-content"
            style={{ display: "flex", gap: 26, alignItems: "flex-end", padding: "0 28px 28px" }}
          >
            {/* Cover */}
            <div
              className="playlist-hero-cover"
              style={{
                width: 190,
                height: 190,
                borderRadius: "var(--r-xl)",
                flexShrink: 0,
                overflow: "hidden",
                background: "var(--bg-elevated)",
                boxShadow: `0 18px 52px rgba(${accentColor},0.38)`,
              }}
            >
              {thumbnail ? (
                <RetryingImage
                  src={thumb(hiResThumb(thumbnail, 500))}
                  alt=""
                  loading="eager"
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    background: `linear-gradient(135deg, rgba(${accentColor},0.8), rgba(${accentColor},0.3))`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {isLiked ? (
                    <Heart size={72} weight="fill" style={{ color: "rgba(255,255,255,0.9)" }} />
                  ) : typeLabel ? (
                    <ClockCounterClockwise size={72} style={{ color: "rgba(255,255,255,0.9)" }} />
                  ) : null}
                </div>
              )}
            </div>

            {/* Info */}
            <div className="playlist-hero-details" style={{ minWidth: 0, flex: 1 }}>
              {/* Type label */}
              <div
                style={{
                  fontSize: "var(--t11)",
                  fontWeight: 600,
                  color: "rgba(255,255,255,0.5)",
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  marginBottom: 8,
                }}
              >
                {typeLabel ?? (isAlbum ? t("album") : t("playlist"))}
              </div>

              {/* Title */}
              <div
                className="playlist-hero-title"
                style={{
                  fontSize: 38,
                  fontWeight: 800,
                  lineHeight: 1.1,
                  marginBottom: 14,
                  color: "#fff",
                  textShadow: "0 2px 20px rgba(0,0,0,0.55)",
                }}
              >
                {title}
              </div>

              {description && (
                <div
                  title={description}
                  style={{
                    maxWidth: 620,
                    marginTop: 2,
                    marginBottom: 10,
                    fontSize: "var(--t13)",
                    lineHeight: 1.5,
                    color: "rgba(255,255,255,0.68)",
                    textShadow: "0 1px 6px rgba(0,0,0,0.5)",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {description}
                </div>
              )}

              {/* Metadata row with pipe separators */}
              <div
                style={{
                  fontSize: "var(--t13)",
                  color: "rgba(255,255,255,0.65)",
                  marginBottom: 20,
                  display: "flex",
                  alignItems: "center",
                  gap: 0,
                  flexWrap: "wrap",
                }}
              >
                {isAlbum && albumArtists && (
                  <>
                    <span
                      onClick={() =>
                        albumArtistBrowseId &&
                        onOpenArtist?.({ browseId: albumArtistBrowseId, artist: albumArtists })
                      }
                      style={{
                        cursor: "default",
                        display: "inline-flex",
                        alignItems: "center",
                        background: `rgba(${accentColor},0.25)`,
                        border: `1px solid rgba(${accentColor},0.42)`,
                        borderRadius: "var(--r-full)",
                        padding: "3px 12px",
                        fontSize: "var(--t13)",
                        fontWeight: 600,
                        color: "var(--accent)",
                        transition: "background 0.15s, border-color 0.15s",
                        marginRight: 10,
                      }}
                      onMouseEnter={(e) => {
                        if (albumArtistBrowseId) {
                          e.currentTarget.style.background = `rgba(${accentColor},0.38)`;
                          e.currentTarget.style.borderColor = `rgba(${accentColor},0.65)`;
                        }
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = `rgba(${accentColor},0.25)`;
                        e.currentTarget.style.borderColor = `rgba(${accentColor},0.42)`;
                      }}
                    >
                      {albumArtists}
                    </span>
                    <span
                      style={{
                        color: "rgba(255,255,255,0.2)",
                        margin: "0 10px",
                        fontSize: "var(--t14)",
                      }}
                    >
                      |
                    </span>
                  </>
                )}
                {isAlbum && year && (
                  <>
                    {musicbrainzDetails?.date && musicbrainzDetails.date.length > 4 ? (
                      <Tooltip text={musicbrainzDetails.date}>
                        <span>{year}</span>
                      </Tooltip>
                    ) : (
                      <span>{year}</span>
                    )}
                    <span
                      style={{
                        color: "rgba(255,255,255,0.2)",
                        margin: "0 10px",
                        fontSize: "var(--t14)",
                      }}
                    >
                      |
                    </span>
                  </>
                )}
                {isAlbum && musicbrainzDetails?.labels?.length > 0 && (
                  <>
                    <Tooltip
                      text={
                        musicbrainzDetails.catalogNumbers?.length
                          ? `${t("recordLabel")} · ${t("catalogNumber")} ${musicbrainzDetails.catalogNumbers.join(", ")}`
                          : t("recordLabel")
                      }
                    >
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                        <Tag size={12} style={{ color: "rgba(255,255,255,0.45)" }} />
                        {musicbrainzDetails.labels.join(", ")}
                      </span>
                    </Tooltip>
                    <span
                      style={{
                        color: "rgba(255,255,255,0.2)",
                        margin: "0 10px",
                        fontSize: "var(--t14)",
                      }}
                    >
                      |
                    </span>
                  </>
                )}
                <span>
                  {total || tracks.length} {t("songs")}
                </span>
                {totalDuration && (
                  <>
                    <span
                      style={{
                        color: "rgba(255,255,255,0.2)",
                        margin: "0 10px",
                        fontSize: "var(--t14)",
                      }}
                    >
                      |
                    </span>
                    <span>{totalDuration}</span>
                  </>
                )}
              </div>

              {/* Action buttons — play left, secondary right */}
              <div
                className="playlist-action-controls"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  flexWrap: "wrap",
                }}
              >
                {/* Left: play + shuffle */}
                <div
                  className="playlist-primary-actions"
                  style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}
                >
                  <button
                    className="playlist-play-action"
                    onClick={() => tracks.length && handlePlay(tracks[0], tracks, playOrigin)}
                    style={{
                      background: `rgba(${accentColor},0.18)`,
                      border: `1px solid rgba(${accentColor},0.38)`,
                      borderRadius: "var(--r-full)",
                      height: 50,
                      padding: "0 28px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 10,
                      cursor: "default",
                      transition: "background 0.18s, border-color 0.18s, transform 0.15s",
                      fontSize: "var(--t15)",
                      fontWeight: 700,
                      color: "var(--accent)",
                      fontFamily: "var(--font)",
                      backdropFilter: "blur(6px)",
                      whiteSpace: "nowrap",
                      flexShrink: 0,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = `rgba(${accentColor},0.3)`;
                      e.currentTarget.style.borderColor = `rgba(${accentColor},0.6)`;
                      e.currentTarget.style.transform = "scale(1.03)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = `rgba(${accentColor},0.18)`;
                      e.currentTarget.style.borderColor = `rgba(${accentColor},0.38)`;
                      e.currentTarget.style.transform = "scale(1)";
                    }}
                  >
                    <Play size={14} weight="fill" style={{ color: "var(--accent)" }} />
                    {t("playAll")}
                  </button>
                  {/* Shuffle: start the collection in a shuffled order without touching the player-bar shuffle toggle */}
                  <button
                    className="playlist-shuffle-action"
                    title={t("shuffle")}
                    onClick={() => {
                      if (!tracks.length) return;
                      const sh = [...tracks].sort(() => Math.random() - 0.5);
                      handlePlay(sh[0], sh, playOrigin);
                    }}
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--r-full)",
                      height: 50,
                      padding: "0 22px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 9,
                      cursor: "default",
                      transition: "background 0.18s, transform 0.15s",
                      fontSize: "var(--t14)",
                      fontWeight: 600,
                      color: "var(--text-secondary)",
                      fontFamily: "var(--font)",
                      whiteSpace: "nowrap",
                      flexShrink: 0,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "rgba(255,255,255,0.12)";
                      e.currentTarget.style.transform = "scale(1.03)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                      e.currentTarget.style.transform = "scale(1)";
                    }}
                  >
                    <Shuffle size={15} />
                    {t("shuffle")}
                  </button>
                  {isAlbum && tracks.length > 0 && (
                    <Tooltip text={t("addAlbumToQueue")}>
                      <button
                        onClick={() => tracks.forEach((track) => enqueue(track, "end"))}
                        style={{
                          background: "rgba(255,255,255,0.06)",
                          border: "1px solid var(--border)",
                          borderRadius: "50%",
                          height: 50,
                          width: 50,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          cursor: "default",
                          transition: "background 0.18s, transform 0.15s",
                          color: "var(--text-secondary)",
                          flexShrink: 0,
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "rgba(255,255,255,0.12)";
                          e.currentTarget.style.transform = "scale(1.03)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                          e.currentTarget.style.transform = "scale(1)";
                        }}
                      >
                        <Queue size={16} />
                      </button>
                    </Tooltip>
                  )}
                </div>

                {/* Right: secondary actions */}
                <div
                  className="playlist-secondary-actions"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    gap: 8,
                    flexWrap: "wrap",
                    flexShrink: 0,
                    // Keep secondary controls visually attached to the right edge when they wrap
                    // below Play and Shuffle in a narrow collection header.
                    marginLeft: "auto",
                  }}
                >
                  {resolvedMixCollectionId && (
                    <Tooltip text={t("mixSetup")}>
                      <button
                        className="playlist-mix-action"
                        type="button"
                        data-testid="mix-toggle"
                        aria-pressed={mixEnabled}
                        disabled={mixLoading}
                        onClick={toggleMix}
                        style={{
                          background: mixEnabled ? "var(--accent)" : "rgba(255,255,255,0.06)",
                          border: `1px solid ${mixEnabled ? "var(--accent)" : "var(--border)"}`,
                          borderRadius: "var(--r-full)",
                          color: mixEnabled ? "#fff" : "var(--text-secondary)",
                          cursor: mixLoading ? "wait" : "default",
                          fontFamily: "var(--font)",
                          fontSize: "var(--t12)",
                          fontWeight: 700,
                          height: 42,
                          opacity: mixLoading ? 0.65 : 1,
                          padding: "0 13px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 6,
                          whiteSpace: "nowrap",
                          flexShrink: 0,
                        }}
                      >
                        <MusicNote size={13} weight="fill" />
                        {t("mix")}
                      </button>
                    </Tooltip>
                  )}
                  {extraActions}
                  {isAlbum && musicbrainzDetails?.id && (
                    <Tooltip text={t("viewOnMusicBrainz")}>
                      <button
                        onClick={() =>
                          openUrl(`https://musicbrainz.org/release/${musicbrainzDetails.id}`).catch(
                            console.error
                          )
                        }
                        style={{
                          background: "rgba(0,0,0,0.3)",
                          border: "0.5px solid rgba(255,255,255,0.15)",
                          borderRadius: "50%",
                          width: 42,
                          height: 42,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          cursor: "default",
                          transition: "background 0.15s",
                          color: "rgba(255,255,255,0.85)",
                          padding: 0,
                          backdropFilter: "blur(6px)",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background = "rgba(255,255,255,0.2)")
                        }
                        onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(0,0,0,0.3)")}
                      >
                        <VinylRecord size={16} />
                      </button>
                    </Tooltip>
                  )}
                  {/* Inline search input */}
                  <div
                    style={{
                      width: searchVisible ? 200 : 0,
                      overflow: "hidden",
                      transition: "width 0.25s cubic-bezier(0.4,0,0.2,1)",
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    <input
                      ref={searchInputRef}
                      value={trackSearch}
                      onChange={(e) => setTrackSearch(e.target.value)}
                      placeholder={t("searchInPlaylist")}
                      style={{
                        background: "rgba(0,0,0,0.35)",
                        border: "0.5px solid rgba(255,255,255,0.18)",
                        borderRadius: "var(--r-full)",
                        padding: "9px 14px",
                        fontSize: "var(--t13)",
                        color: "#fff",
                        outline: "none",
                        width: 200,
                        flexShrink: 0,
                        fontFamily: "var(--font)",
                      }}
                    />
                  </div>
                  {searchVisible && trackSearch && (
                    <span
                      style={{
                        fontSize: "var(--t12)",
                        color: "rgba(255,255,255,0.5)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {visibleTracks.length} {t("xOfY")} {tracks.length}
                    </span>
                  )}
                  {/* Search toggle */}
                  <Tooltip text={t("searchInPlaylist")}>
                    <button
                      onClick={() => {
                        setSearchVisible((v) => !v);
                        if (searchVisible) setTrackSearch("");
                      }}
                      style={{
                        background: searchVisible ? "rgba(255,255,255,0.16)" : "rgba(0,0,0,0.3)",
                        border: "0.5px solid rgba(255,255,255,0.15)",
                        borderRadius: "50%",
                        width: 42,
                        height: 42,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "default",
                        transition: "background 0.15s",
                        color: "rgba(255,255,255,0.85)",
                        padding: 0,
                        backdropFilter: "blur(6px)",
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.background = "rgba(255,255,255,0.2)")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.background = searchVisible
                          ? "rgba(255,255,255,0.16)"
                          : "rgba(0,0,0,0.3)")
                      }
                    >
                      <MagnifyingGlass size={15} />
                    </button>
                  </Tooltip>

                  {/* Download / downloaded state */}
                  {onDownloadAll &&
                    tracks.length > 0 &&
                    (() => {
                      const allCached =
                        cachedSongIds && tracks.every((tr) => cachedSongIds.has(tr.videoId));
                      const someDownloading =
                        downloadingIds && tracks.some((tr) => downloadingIds.has(tr.videoId));
                      const btnBase = {
                        borderRadius: "var(--r-full)",
                        height: 42,
                        display: "flex",
                        alignItems: "center",
                        padding: "0 18px",
                        gap: 8,
                        fontSize: "var(--t13)",
                        fontWeight: 600,
                        cursor: "default",
                        transition: "background 0.15s, border-color 0.15s",
                        fontFamily: "var(--font)",
                        backdropFilter: "blur(6px)",
                        border: "0.5px solid rgba(255,255,255,0.15)",
                        whiteSpace: "nowrap",
                        flexShrink: 0,
                      };
                      return allCached ? (
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <div
                            style={{
                              ...btnBase,
                              cursor: "default",
                              color: "var(--status-success)",
                              background: "rgba(76,175,80,0.12)",
                              border: "0.5px solid rgba(76,175,80,0.3)",
                            }}
                          >
                            <CheckCircle size={14} weight="fill" />
                            {t("downloaded")}
                          </div>
                          {onRemoveAll && (
                            <Tooltip text={t("removeDownload")}>
                              <button
                                onClick={() => onRemoveAll(tracks)}
                                style={{
                                  background: "rgba(0,0,0,0.3)",
                                  border: "0.5px solid rgba(255,255,255,0.15)",
                                  borderRadius: "50%",
                                  width: 42,
                                  height: 42,
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  cursor: "default",
                                  transition: "background 0.15s",
                                  color: "rgba(255,255,255,0.7)",
                                  padding: 0,
                                  backdropFilter: "blur(6px)",
                                }}
                                onMouseEnter={(e) => {
                                  e.currentTarget.style.background = "rgba(224,82,82,0.25)";
                                  e.currentTarget.style.color = "var(--status-danger)";
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.background = "rgba(0,0,0,0.3)";
                                  e.currentTarget.style.color = "rgba(255,255,255,0.7)";
                                }}
                              >
                                <Trash size={14} />
                              </button>
                            </Tooltip>
                          )}
                        </div>
                      ) : (
                        <button
                          onClick={() => onDownloadAll(tracks)}
                          disabled={someDownloading}
                          style={{
                            ...btnBase,
                            background: "rgba(0,0,0,0.3)",
                            color: "rgba(255,255,255,0.85)",
                            opacity: someDownloading ? 0.65 : 1,
                            cursor: someDownloading ? "default" : "default",
                          }}
                          onMouseEnter={(e) => {
                            if (!someDownloading)
                              e.currentTarget.style.background = "rgba(255,255,255,0.14)";
                          }}
                          onMouseLeave={(e) =>
                            (e.currentTarget.style.background = "rgba(0,0,0,0.3)")
                          }
                        >
                          {someDownloading ? (
                            <DownloadSimple
                              size={14}
                              style={{ animation: "pulse 1s ease-in-out infinite" }}
                            />
                          ) : (
                            <DownloadSimple size={14} />
                          )}
                          {t("downloadAll")}
                        </button>
                      );
                    })()}

                  {/* Refresh */}
                  {cached && onRefresh && (
                    <Tooltip text={t("refresh")}>
                      <button
                        onClick={onRefresh}
                        style={{
                          background: "rgba(0,0,0,0.3)",
                          border: "0.5px solid rgba(255,255,255,0.15)",
                          borderRadius: "50%",
                          width: 42,
                          height: 42,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          cursor: "default",
                          transition: "background 0.15s, transform 0.15s",
                          color: "rgba(255,255,255,0.85)",
                          padding: 0,
                          backdropFilter: "blur(6px)",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "rgba(255,255,255,0.14)";
                          e.currentTarget.style.transform = "rotate(30deg)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = "rgba(0,0,0,0.3)";
                          e.currentTarget.style.transform = "rotate(0deg)";
                        }}
                      >
                        <ArrowClockwise size={14} />
                      </button>
                    </Tooltip>
                  )}
                  {onCollectionActions && (
                    <Tooltip text={t("moreActions")}>
                      <button
                        type="button"
                        aria-label={t("moreActions")}
                        onClick={onCollectionActions}
                        style={{
                          background: "rgba(0,0,0,0.3)",
                          border: "0.5px solid rgba(255,255,255,0.15)",
                          borderRadius: "50%",
                          width: 42,
                          height: 42,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          cursor: "default",
                          transition: "background 0.15s",
                          color: "rgba(255,255,255,0.85)",
                          padding: 0,
                          backdropFilter: "blur(6px)",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background = "rgba(255,255,255,0.14)")
                        }
                        onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(0,0,0,0.3)")}
                      >
                        <DotsThreeVertical size={16} />
                      </button>
                    </Tooltip>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Loading progress */}
      {loading && !cached && (
        <div style={{ padding: "0 28px 12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontSize: "var(--t11)", color: "var(--text-muted)" }}>
              {t("fetchingSongs")}
            </span>
            <span style={{ fontSize: "var(--t11)", color: "var(--accent)", fontWeight: 500 }}>
              {progress}%
            </span>
          </div>
          <div
            style={{
              height: 3,
              background: "var(--bg-elevated)",
              borderRadius: "var(--r-full)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                borderRadius: "var(--r-full)",
                background: "linear-gradient(90deg,var(--accent),#c020e0)",
                width: `${progress}%`,
                transition: "width 0.4s ease",
              }}
            />
          </div>
        </div>
      )}

      {/* Column headers */}
      <div
        ref={tableHeaderRef}
        style={{
          display: "grid",
          gridTemplateColumns: tableGridColumns({
            hasSelection: Boolean(onToggleSelect),
            showAlbumColumn,
            showBpmColumn,
            showKeyColumn,
          }),
          gap: 12,
          padding: "8px 16px",
          margin: "0 12px",
          borderBottom: "0.5px solid var(--border)",
          fontSize: "var(--t11)",
          fontWeight: 600,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        {onToggleSelect &&
          (() => {
            const allSelected =
              visibleTracks.length > 0 &&
              visibleTracks.every((tr) => selectedTracks?.has(tr.videoId));
            return (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "default",
                }}
                onClick={() => onSelectAll?.(visibleTracks, allSelected)}
                title={allSelected ? t("deselectAll") : t("selectAll")}
              >
                {allSelected ? (
                  <CheckCircle size={18} weight="fill" style={{ color: "var(--accent)" }} />
                ) : (
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      border: "1.5px solid var(--text-muted)",
                      background: "var(--bg-elevated)",
                    }}
                  />
                )}
              </div>
            );
          })()}
        <div style={{ textAlign: "center" }}>{showNum ? "#" : ""}</div>
        {sortableHead("title", t("colTitle"))}
        {showBpmColumn && <div style={{ textAlign: "center" }}>{t("colBpm")}</div>}
        {showKeyColumn && <div style={{ textAlign: "center" }}>{t("colKey")}</div>}
        {showAlbumColumn && sortableHead("album", t("colAlbum"))}
        <div></div>
        {sortableHead("duration", <Clock size={13} />, "right", t("colDuration"))}
      </div>

      {/* Track list (virtualized — only on-screen rows are mounted) */}
      <div style={{ padding: "8px 12px 32px" }}>
        <div
          ref={listInnerRef}
          style={{ position: "relative", height: rowVirtualizer.getTotalSize() }}
        >
          {rowVirtualizer.getVirtualItems().map((vi) => {
            const i = vi.index;
            const tr = visibleTracks[i];
            return (
              <div
                key={vi.key}
                data-index={i}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: 68,
                  transform: `translateY(${vi.start - listScrollMargin}px)`,
                }}
              >
                {tr ? (
                  <TableRow
                    track={tr}
                    index={i}
                    isPlaying={isPlaying && currentTrack?.videoId === tr.videoId}
                    onPlay={() => handlePlay(tr, visibleTracks, playOrigin)}
                    onOpenArtist={onOpenArtist}
                    onOpenAlbum={onOpenAlbum}
                    showAlbumColumn={showAlbumColumn}
                    onContextMenu={onTrackContextMenu}
                    isCached={cachedSongIds?.has(tr.videoId)}
                    isDownloading={downloadingIds?.has(tr.videoId)}
                    isPremiumOnly={premiumSongIds?.has(tr.videoId)}
                    onDownload={onDownloadSong}
                    selected={selectedTracks?.has(tr.videoId)}
                    onToggleSelect={onToggleSelect ? () => onToggleSelect(tr) : undefined}
                    mixAnalysis={
                      mixConfig?.trackAnalysis?.[
                        mixTrackOrder.find((item) => item.videoId === tr.videoId)?.instanceId
                      ]
                    }
                    showBpmColumn={showBpmColumn}
                    showKeyColumn={showKeyColumn}
                  />
                ) : (
                  <SkeletonRow />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
