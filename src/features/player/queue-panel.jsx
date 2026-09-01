import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Button,
  ChipLabel,
  ChipRoot,
  ScrollShadowRoot,
  ToggleButton,
  ToggleButtonGroupRoot,
} from "@heroui/react";

import {
  CaretLineUp,
  DotsThreeVertical,
  GripLines,
  Heart,
  Sliders,
  Trash,
} from "@/shared/icons/icons.jsx";
import { API } from "@/shared/api/client.js";
import { thumb } from "@/shared/api/thumbnails.js";
import { RetryingImage } from "@/shared/ui/retrying-image.jsx";
import { Tooltip } from "@/shared/ui/tooltip.jsx";
import { ContextMenu, CtxItem } from "@/shared/ui/context-menu.jsx";
import { ExplicitBadge } from "@/features/music/components/rows.jsx";
import { dissolve } from "@/shared/lib/particle-burst.js";
import { useAnimations, useZoom } from "@/features/settings/display-context.jsx";
import { useLang } from "@/shared/i18n/context.jsx";
import { FadeEditorModal } from "./fade-editor-modal.jsx";
import { NowPlayingSidebarCard } from "./now-playing-sidebar-card.jsx";
import { AboutSongDetails } from "./about-song-details.jsx";
import {
  usePlaybackStatus,
  useQueueState,
  usePlaybackConfig,
  usePlayerActions,
} from "./player-context.jsx";

const QUEUE_ROW_H = 52;
const QUEUE_HEADER_H = 34;
const QUEUE_CONTEXT_H = 38;

function TrackArtwork({ thumbnail, className }) {
  return (
    <div className={`relative overflow-hidden bg-[var(--placeholder-gradient)] ${className || ""}`}>
      {thumbnail && (
        <RetryingImage
          src={thumb(thumbnail)}
          alt=""
          decoding="async"
          className="absolute inset-0 w-full h-full object-cover"
        />
      )}
    </div>
  );
}

// Plain button rather than HeroUI's, for the same reason the track rows use one: a queued
// playlist can be thousands of entries, and each react-aria button brings its own hooks,
// generated id and attribute set. aria-label carries the accessible name that isIconOnly
// would otherwise have demanded.
function QueueIconButton({ label, onClick, className = "", children }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={`h-7 min-w-7 px-1 rounded-[var(--r-sm)] border-0 bg-transparent cursor-default inline-flex items-center justify-center transition-[background-color,color,transform] duration-150 hover:bg-hover active:scale-[0.90] ${className}`}
    >
      {children}
    </button>
  );
}

function QueueRow({
  track,
  globalIdx,
  isDraggable,
  dimmed,
  isActive,
  isBeingDragged,
  dropBefore,
  dropAfter,
  onPointerDown,
  onPlay,
  isLiked,
  onToggleLike,
  onOpenMenu,
  menuOpen,
  fadeSecs,
  // Defaults to {} so a call site that forgets to pass it loses the row action buttons'
  // accessible names — which the console already warns about — instead of crashing the app.
  labels = {},
}) {
  return (
    <div
      data-queue-idx={globalIdx}
      onClick={onPlay}
      onContextMenu={isDraggable ? (e) => { e.preventDefault(); onOpenMenu({ x: e.clientX, y: e.clientY, globalIdx }); } : undefined}
      onPointerDown={isDraggable ? (e) => onPointerDown(e, globalIdx) : undefined}
      style={{ height: QUEUE_ROW_H }}
      className={`group/qrow relative flex items-center gap-2 pl-2.5 pr-3 rounded-[var(--r-md)] cursor-default select-none transition-[background-color,opacity] ${
        isActive ? "bg-accent-dim" : "bg-transparent hover:bg-[var(--fill-subtle)]"
      } ${isBeingDragged ? "opacity-30" : dimmed ? "opacity-45 hover:opacity-100" : ""}`}
    >
      {dropBefore && <div className="absolute -top-px inset-x-0 h-0.5 rounded-full bg-accent pointer-events-none" />}
      {dropAfter && <div className="absolute -bottom-px inset-x-0 h-0.5 rounded-full bg-accent pointer-events-none" />}
      {/* Drag handle (the whole row is draggable; this is just the affordance) */}
      <div
        className={`shrink-0 px-px py-0.5 touch-none transition-opacity ${isDraggable ? "cursor-grab opacity-40 group-hover/qrow:opacity-100" : "opacity-0"}`}
      >
        <GripLines size={13} className="block pointer-events-none text-muted" />
      </div>

      {/* Thumbnail */}
      <TrackArtwork
        key={track.thumbnail || "missing-artwork"}
        thumbnail={track.thumbnail}
        className="w-9 h-9 shrink-0 rounded-[var(--r-sm)]"
      />

      {/* Title + artist */}
      <div className="flex-1 min-w-0">
        <div
          className={`flex items-center gap-1 overflow-hidden text-t12 font-medium ${isActive ? "text-accent" : "text-primary"}`}
        >
          <span className="truncate min-w-0">{track.title}</span>
          {track.isExplicit && <ExplicitBadge />}
        </div>
        <div className="text-t11 text-secondary truncate">{track.artists}</div>
      </div>

      {/* Custom-crossfade indicator (set via right-click) */}
      {fadeSecs != null && (
        <span
          title={`Crossfade: ${fadeSecs}s`}
          className="shrink-0 inline-flex items-center gap-0.5 text-[10px] font-semibold text-accent px-1.5 py-0.5 rounded-[var(--r-sm)] bg-accent-dim"
        >
          <Sliders size={10} weight="bold" />
          {fadeSecs}s
        </span>
      )}

      {/* Duration */}
      {track.duration && (
        <div className="shrink-0 min-w-[28px] text-t11 text-muted text-right">{track.duration}</div>
      )}

      {/* Like button */}
      <span
        className="shrink-0 inline-flex"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <QueueIconButton
          label={isLiked ? labels.unlike : labels.like}
          onClick={() => onToggleLike?.(track)}
          className={isLiked ? "text-accent" : "text-muted hover:text-secondary"}
        >
          <Heart size={14} weight={isLiked ? "fill" : "regular"} />
        </QueueIconButton>
      </span>

      {/* Queue actions */}
      {isDraggable && (
        <span
          className="shrink-0 inline-flex"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <QueueIconButton
            label={labels.more}
            onClick={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              onOpenMenu({ x: rect.left, y: rect.bottom + 4, globalIdx });
            }}
            className={`text-muted hover:text-secondary ${menuOpen ? "bg-hover text-primary" : ""}`}
          >
            <DotsThreeVertical size={15} weight="bold" />
          </QueueIconButton>
        </span>
      )}
    </div>
  );
}

export function QueuePanel({
  likedIds,
  onToggleLike,
  visible,
  nowPlayingContextTitle,
  onOpenArtist,
  canvasEnabled,
  canvasSource,
}) {
  const { track: currentTrack, playbackOrigin } = usePlaybackStatus();
  const { queue } = useQueueState();
  const { crossfade = 0, crossfadeOverrides = {} } = usePlaybackConfig();
  const { setQueue, setTrack, setCrossfadeOverride, removeCrossfadeOverride } = usePlayerActions();
  const t = useLang();
  const zoom = useZoom();
  const anim = useAnimations();
  // Built once here rather than a translation hook per row — a queued playlist can be
  // thousands of them.
  const rowLabels = useMemo(
    () => ({ like: t("like"), unlike: t("unlike"), remove: t("removeFromQueue"), more: t("rowMoreActions") }),
    [t]
  );
  const [panelTab, setPanelTab] = useState("queue");
  // Keep the list mounted briefly during the dock slide-out, then stop rendering
  // hidden queue rows so large queues do not keep doing work off-screen.
  const [mountList, setMountList] = useState(visible);
  useEffect(() => {
    if (visible) {
      setMountList(true);
      return;
    }
    const id = setTimeout(() => setMountList(false), 450);
    return () => clearTimeout(id);
  }, [visible]);
  const [fadeEdit, setFadeEdit] = useState(null); // { from, to } — open the per-transition fade editor
  const [rowMenu, setRowMenu] = useState(null);
  const fadeKey = (a, b) => `${a?.videoId}__${b?.videoId}`;
  const [songDesc, setSongDesc] = useState(null); // null=loading, ""=none, str=text
  const [songDescId, setSongDescId] = useState(null);
  const [songDescError, setSongDescError] = useState(null);
  const [dropOffset, setDropOffset] = useState(null);
  const [dragIndex, setDragIndex] = useState(null);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [fabPos, setFabPos] = useState(null); // {left,width,bottom} for the portaled scroll-top pill
  const isDragging = useRef(false);
  const suppressClickRef = useRef(false);
  const listRef = useRef(null);
  const nowPlayingOffsetRef = useRef(0);
  const dropOffsetRef = useRef(null);

  // Fetch song description when switching to About tab or track changes
  const fetchSongDesc = useCallback(
    (videoId, force = false) => {
      if (!videoId) return;
      if (!force && songDescId === videoId) return;
      setSongDesc(null);
      setSongDescError(null);
      setSongDescId(videoId);
      fetch(`${API}/song/credits/${videoId}`)
        .then((r) => r.json())
        .then((d) => {
          if (d.error) setSongDescError(d.error);
          else setSongDesc(d.description || "");
        })
        .catch(() => setSongDesc(""));
    },
    [songDescId]
  );

  useEffect(() => {
    if (panelTab !== "about" || !currentTrack?.videoId) return;
    fetchSongDesc(currentTrack.videoId);
  }, [panelTab, currentTrack?.videoId]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    // The pill is portaled to <body> (to escape the panel's overflow+radius clip, which
    // would kill its backdrop-filter), so we position it over the list's bottom edge.
    const updatePos = () => {
      const r = el.getBoundingClientRect();
      setFabPos({ left: r.left, width: r.width, bottom: window.innerHeight - r.bottom });
    };
    const onScroll = () => {
      setShowScrollTop(el.scrollTop > nowPlayingOffsetRef.current + QUEUE_HEADER_H + QUEUE_ROW_H);
      updatePos();
    };
    el.addEventListener("scroll", onScroll);
    window.addEventListener("resize", updatePos);
    return () => {
      el.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", updatePos);
    };
  }, []);

  const currentIdx = queue.findIndex((t) => t.videoId === currentTrack?.videoId);
  const { items, offsets, nowPlayingOffset } = useMemo(() => {
    const list = [];
    if (currentIdx > 0) {
      list.push({ kind: "header", key: "played-header", label: t("previouslyPlayed"), section: "played" });
      for (let index = 0; index < currentIdx; index += 1) {
        list.push({ kind: "row", key: `played-${queue[index].videoId || index}`, track: queue[index], globalIdx: index, dimmed: true });
      }
    }
    let nowOffset = 0;
    if (currentTrack && currentIdx >= 0) {
      list.push({ kind: "header", key: "now-header", label: t("nowPlaying"), marksNowPlaying: true });
      list.push({ kind: "row", key: `now-${currentTrack.videoId}`, track: currentTrack, globalIdx: currentIdx, active: true, dimmed: true });
    }
    const upNextCount = queue.length - currentIdx - 1;
    if (upNextCount > 0) {
      list.push({ kind: "header", key: "next-header", label: t("upNext"), count: upNextCount, section: "next" });
      for (let index = currentIdx + 1; index < queue.length; index += 1) {
        list.push({ kind: "row", key: `next-${queue[index].videoId || index}`, track: queue[index], globalIdx: index });
      }
    }
    const nextOffsets = [];
    let offset = 0;
    list.forEach((item) => {
      nextOffsets.push(offset);
      if (item.marksNowPlaying) nowOffset = offset;
      offset += item.kind === "header" ? QUEUE_HEADER_H : QUEUE_ROW_H;
    });
    return { items: list, offsets: nextOffsets, nowPlayingOffset: nowOffset };
  }, [currentIdx, currentTrack, queue, t]);
  nowPlayingOffsetRef.current = nowPlayingOffset;
  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => listRef.current,
    estimateSize: (index) => (items[index]?.kind === "header" ? QUEUE_HEADER_H : QUEUE_ROW_H),
    overscan: 8,
  });

  // "Playing from" context — derived from the trackIds snapshotted when the album was played, not
  // the live (shuffleable, editable) queue, so the position keeps meaning after a shuffle.
  const albumOrigin = playbackOrigin?.kind === "album" ? playbackOrigin : null;
  const albumTrackNumber = albumOrigin
    ? albumOrigin.trackIds.indexOf(currentTrack?.videoId) + 1
    : 0;

  // Open the per-transition fade editor for globalIdx → globalIdx+1.
  const openFadeEdit = (globalIdx) => {
    const from = queue[globalIdx],
      to = queue[globalIdx + 1];
    if (from && to) setFadeEdit({ from, to });
  };

  const removeTrack = useCallback(
    (videoId) => {
      setQueue((q) => q.filter((t) => t.videoId !== videoId));
    },
    [setQueue]
  );

  const removeWithEffect = useCallback((globalIdx, videoId) => {
    const row = listRef.current?.querySelector(`[data-queue-idx="${globalIdx}"]`);
    if (anim && row) dissolve(row, () => removeTrack(videoId));
    else removeTrack(videoId);
  }, [anim, removeTrack]);

  const handlePointerDown = useCallback(
    (e, globalIdx) => {
      if (e.button !== 0) return; // ignore right/middle click so the context menu (fade editor) fires
      e.preventDefault();
      isDragging.current = false;
      dropOffsetRef.current = null;
      setDropOffset(null);

      const startY = e.clientY;

      const onMove = (me) => {
        if (Math.abs(me.clientY - startY) > 4) {
          isDragging.current = true;
          setDragIndex(globalIdx);
        }
        const container = listRef.current;
        if (!isDragging.current || !container) return;
        const y = me.clientY - container.getBoundingClientRect().top + container.scrollTop - (albumOrigin && albumTrackNumber > 0 ? QUEUE_CONTEXT_H : 0);
        let offset = null;
        for (let index = 0; index < items.length; index += 1) {
          const item = items[index];
          if (item.kind !== "row") continue;
          if (y <= offsets[index] + QUEUE_ROW_H / 2) {
            offset = item.globalIdx;
            break;
          }
          offset = item.globalIdx + 1;
        }
        dropOffsetRef.current = offset;
        setDropOffset(offset);
      };

      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        const target = dropOffsetRef.current;
        const didDrag = isDragging.current;
        if (didDrag && target != null && target !== globalIdx && target !== globalIdx + 1) {
          setQueue((q) => {
            const next = [...q];
            const [moved] = next.splice(globalIdx, 1);
            // Compensate for the removed item: when dropping below the origin, every
            // index at/after `globalIdx` shifted up by one, so the visual slot is target-1.
            const targetIdx = target > globalIdx ? target - 1 : target;
            next.splice(targetIdx, 0, moved);
            return next;
          });
        }
        // Suppress the click that fires right after a drag so it doesn't also start playback.
        if (didDrag) {
          suppressClickRef.current = true;
          setTimeout(() => {
            suppressClickRef.current = false;
          }, 0);
        }
        isDragging.current = false;
        setDragIndex(null);
        dropOffsetRef.current = null;
        setDropOffset(null);
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [albumOrigin, albumTrackNumber, items, offsets, setQueue]
  );

  return (
    <div className="flex flex-col h-full relative">
      {/* Header */}
      <div className="px-3 pt-11 shrink-0">
        <div className="flex items-center gap-1.5 mb-2.5">
          {/* HeroUI segmented tabs */}
          <ToggleButtonGroupRoot
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[panelTab]}
            onSelectionChange={(keys) => {
              const v = [...keys][0];
              if (v) setPanelTab(v);
            }}
            size="sm"
            fullWidth
            className="flex-1"
          >
            <ToggleButton id="queue" className="flex-1">
              {t("queue")}
            </ToggleButton>
            <ToggleButton id="about" className="flex-1">
              {t("aboutSong")}
            </ToggleButton>
          </ToggleButtonGroupRoot>
          {/* Clear queue icon button — always rendered to keep pill width stable */}
          <Tooltip text={t("clearQueue")}>
            <Button
              variant="ghost"
              size="sm"
              isIconOnly
              onPress={() => setQueue([])}
              className={`shrink-0 rounded-[var(--r-md)] text-muted hover:text-[var(--status-danger)]! ${panelTab === "queue" ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}`}
            >
              <Trash size={13} />
            </Button>
          </Tooltip>
        </div>
      </div>

      {/* About Song tab */}
      {panelTab === "about" && (
        <div className="scrollable flex-1 overflow-y-auto px-4 pt-4 pb-6">
          {currentTrack ? (
            <>
              <div className="queue-about__now-playing">
                <NowPlayingSidebarCard
                  track={currentTrack}
                  contextTitle={nowPlayingContextTitle || currentTrack.album || t("nowPlaying")}
                  isLiked={likedIds?.has(currentTrack.videoId)}
                  onToggleLike={onToggleLike}
                  saveLabel={t("save")}
                  canvasEnabled={canvasEnabled}
                  canvasSource={canvasSource}
                />
              </div>

              <AboutSongDetails
                track={currentTrack}
                description={songDesc}
                descriptionError={songDescError}
                onOpenArtist={onOpenArtist}
                onRetryDescription={() => {
                  setSongDescId(null);
                  fetchSongDesc(currentTrack.videoId, true);
                }}
              />
            </>
          ) : (
            <div className="text-t13 text-muted text-center mt-10">{t("selectSong")}</div>
          )}
        </div>
      )}

      {mountList && panelTab === "queue" && (
        <ScrollShadowRoot
          ref={listRef}
          size={28}
          className="scrollable flex-1 overflow-y-auto px-2 pt-1 pb-4"
        >
          {albumOrigin && albumTrackNumber > 0 && (
            <div className="flex items-center gap-2 px-1.5 pt-1 pb-2.5 min-w-0">
              {albumOrigin.thumbnail && (
                <img
                  src={thumb(albumOrigin.thumbnail)}
                  alt=""
                  className="w-6 h-6 rounded-[var(--r-sm)] object-cover shrink-0"
                />
              )}
              <span className="text-t11 text-secondary truncate min-w-0">
                {t("playingFrom", { title: albumOrigin.title })} ·{" "}
                {t("trackOfTotal", { n: albumTrackNumber, total: albumOrigin.trackIds.length })}
              </span>
            </div>
          )}
          {queue.length === 0 ? (
            <div className="p-6 text-t13 text-muted text-center">{t("emptyQueue")}</div>
          ) : (
            <div style={{ height: rowVirtualizer.getTotalSize(), position: "relative" }}>
              {rowVirtualizer.getVirtualItems().map((virtualItem) => {
                const item = items[virtualItem.index];
                return (
                  <div
                    key={item.key}
                    style={{ position: "absolute", top: 0, left: 0, width: "100%", transform: `translateY(${virtualItem.start}px)` }}
                  >
                    {item.kind === "header" ? (
                      <div className="group/qsec flex h-[34px] items-center justify-between px-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
                        <span>{item.label}</span>
                        {item.count != null && <ChipRoot size="sm" variant="soft"><ChipLabel>{item.count}</ChipLabel></ChipRoot>}
                        {item.section === "played" && (
                          <Tooltip text={t("clearPlayed")}>
                            <Button variant="ghost" size="sm" isIconOnly onPress={() => setQueue((q) => q.slice(currentIdx))} className="shrink-0 h-6 min-w-6 rounded-[var(--r-sm)] text-muted opacity-0 group-hover/qsec:opacity-100 hover:text-[var(--status-danger)]!">
                              <Trash size={11} />
                            </Button>
                          </Tooltip>
                        )}
                      </div>
                    ) : (
                      <QueueRow
                        labels={rowLabels}
                        track={item.track}
                        globalIdx={item.globalIdx}
                        isDraggable={!item.active}
                        dimmed={item.dimmed}
                        isActive={item.active}
                        isBeingDragged={dragIndex === item.globalIdx}
                        dropBefore={dropOffset === item.globalIdx}
                        dropAfter={dropOffset === item.globalIdx + 1 && item.globalIdx === queue.length - 1}
                        onPointerDown={handlePointerDown}
                        onPlay={() => {
                          if (!suppressClickRef.current) setTrack(item.track);
                        }}
                        isLiked={likedIds?.has(item.track.videoId)}
                        onToggleLike={onToggleLike}
                        onOpenMenu={setRowMenu}
                        menuOpen={rowMenu?.globalIdx === item.globalIdx}
                        fadeSecs={crossfadeOverrides[fadeKey(item.track, queue[item.globalIdx + 1])]?.secs ?? null}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </ScrollShadowRoot>
      )}

      {/* Scroll-to-top pill — portaled to <body> so it escapes the panel's overflow+radius
          clip (which otherwise disables backdrop-filter on descendants). */}
      {visible &&
        panelTab === "queue" &&
        showScrollTop &&
        fabPos &&
        createPortal(
          <div
            style={{
              position: "fixed",
              left: fabPos.left,
              width: fabPos.width,
              bottom: fabPos.bottom + 16,
              display: "flex",
              justifyContent: "center",
              zIndex: 200,
              pointerEvents: "none",
            }}
            className="animate-[pillRiseIn_0.26s_cubic-bezier(0.22,1,0.36,1)]"
          >
            <div className="relative pointer-events-auto rounded-full shadow-[0_6px_22px_rgba(0,0,0,0.45)]">
              {/* Dedicated frosted backdrop layer — a plain div (no transform/isolation/clip
                ancestors here), so backdrop-filter actually samples the list behind it. */}
              <div className="absolute inset-0 rounded-full bg-[rgba(255,255,255,0.13)] backdrop-blur-2xl" />
              <Button
                variant="ghost"
                size="sm"
                onPress={() => {
                  const container = listRef.current;
                  container?.scrollTo({
                    top: nowPlayingOffsetRef.current + (albumOrigin && albumTrackNumber > 0 ? QUEUE_CONTEXT_H : 0),
                    behavior: "smooth",
                  });
                }}
                className="relative gap-2 h-9! px-4 rounded-full text-t13 font-semibold text-primary! border-none! bg-transparent! hover:bg-[rgba(255,255,255,0.09)]!"
              >
                <CaretLineUp size={15} weight="bold" className="text-accent" /> {t("scrollToTop")}
              </Button>
            </div>
          </div>,
          document.body
        )}

      {rowMenu && (() => {
        const track = queue[rowMenu.globalIdx];
        if (!track) return null;
        return (
          <ContextMenu
            x={rowMenu.x}
            y={rowMenu.y}
            zoom={zoom}
            onClose={() => setRowMenu(null)}
            ariaLabel={t("rowMoreActions")}
          >
            {queue[rowMenu.globalIdx + 1] && (
              <CtxItem
                icon={Sliders}
                label={t("crossfade")}
                onSelect={() => {
                  openFadeEdit(rowMenu.globalIdx);
                  setRowMenu(null);
                }}
              />
            )}
            <CtxItem
              icon={Trash}
              label={t("removeFromQueue")}
              danger
              onSelect={() => {
                removeWithEffect(rowMenu.globalIdx, track.videoId);
                setRowMenu(null);
              }}
            />
          </ContextMenu>
        );
      })()}

      {fadeEdit && (
        <FadeEditorModal
          from={fadeEdit.from}
          to={fadeEdit.to}
          globalDefault={crossfade}
          current={crossfadeOverrides[fadeKey(fadeEdit.from, fadeEdit.to)]?.secs ?? null}
          onSave={(secs) =>
            setCrossfadeOverride?.(
              fadeEdit.from.videoId,
              fadeEdit.to.videoId,
              secs,
              fadeEdit.from.title,
              fadeEdit.to.title
            )
          }
          onClear={() => removeCrossfadeOverride?.(fadeKey(fadeEdit.from, fadeEdit.to))}
          onClose={() => setFadeEdit(null)}
        />
      )}
    </div>
  );
}
