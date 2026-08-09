import { memo } from "react";
import { LyricsOverlay } from "@/features/lyrics/LyricsOverlay.jsx";
import { CoverView } from "@/features/player/player-ui.jsx";
import { hiResThumb } from "@/features/player/cover-art.js";
import { SIDEBAR_COLLAPSED } from "./shell-constants.js";
import { VideoSyncView } from "@/features/player/video-sync.jsx";

export const PlayerOverlay = memo(function PlayerOverlay({
  overlayOpen,
  fullscreen,
  sidebarCollapsed,
  sidebarWidth,
  queueOpen,
  queueWidth,
  queueResizing,
  animations,
  currentTrack,
  ambientBackground,
  splitView,
  splitRatio,
  splitResizing,
  startSplitResize,
  showLyrics,
  showVideoView,
  videoSync,
  videoLyricsStyle,
  audioRef,
  isPlaying,
  setOverlayOpen,
  lyricsFontSize,
  lyricsProviders,
  lyricsRefetchKey,
  addToast,
  language,
  forcedLyricsProvider,
  setCurrentLyricsSource,
  setFailedLyricsProviders,
  showLyricsTranslation,
  lyricsTranslationLang,
  lyricsTranslationFontSize,
  showRomaji,
  lyricsRomajiFontSize,
  setIsCustomLyrics,
  importLyricsRef,
  removeCustomLyricsRef,
  openLyricsBrowserRef,
  showAgentTags,
  ambientVisualizer,
  syllableZoom,
  fluidLyrics,
  playerVisible,
  handleInstrumentalChange,
  vizConfig,
}) {
  return (
    <div
      data-sidebar-resize-offset={
        overlayOpen && !fullscreen && !sidebarCollapsed ? "" : undefined
      }
      style={{
        position: "absolute",
        top: overlayOpen ? (fullscreen ? 0 : 8) : "100%",
        left: fullscreen ? 0 : (sidebarCollapsed ? SIDEBAR_COLLAPSED : sidebarWidth) + 4,
        right: fullscreen ? 0 : queueOpen ? queueWidth + 16 : 8,
        bottom: fullscreen ? 0 : 112,
        zIndex: fullscreen ? 102 : 100,
        overflow: "hidden",
        borderRadius: fullscreen ? 0 : "var(--r-xl)",
        transition: queueResizing
          ? "top 0.42s cubic-bezier(0.4,0,0.2,1), left 0.3s ease"
          : animations
            ? "top 0.42s cubic-bezier(0.4,0,0.2,1), right 0.3s ease, left 0.3s ease"
            : "top 0.1s ease",
        pointerEvents: overlayOpen ? "all" : "none",
      }}
    >
      {/* Shared static background — stays fixed during crossfade */}
      {currentTrack && !ambientBackground && (
        <>
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "#0d0d0d",
              pointerEvents: "none",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              backgroundImage: currentTrack.thumbnail
                ? `url(${hiResThumb(currentTrack.thumbnail)})`
                : "none",
              backgroundSize: "cover",
              backgroundPosition: "center",
              filter: "blur(24px) brightness(0.5)",
              transform: "scale(1.08)",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "rgba(0,0,0,0.55)",
              pointerEvents: "none",
            }}
          />
        </>
      )}
      {currentTrack &&
        (() => {
          const coverSplitActive = fullscreen && splitView && !showVideoView;
          const videoLyricsOn = showVideoView && showLyrics;
          const videoSplitActive = videoLyricsOn && videoLyricsStyle === "split";
          const videoCaptionsActive = videoLyricsOn && videoLyricsStyle === "captions";
          const splitActive = coverSplitActive || videoSplitActive;
          const coverPct = `${(splitRatio * 100).toFixed(2)}%`;
          const lyricsPct = `${((1 - splitRatio) * 100).toFixed(2)}%`;
          const widthTransition = splitResizing ? "none" : "width 0.4s cubic-bezier(0.4,0,0.2,1)";
          const paneTransition = `opacity 0.35s ease, ${widthTransition}`;
          // The panes remain mounted for their opacity transition, but their expensive visual
          // work must only run while that pane can actually be seen.
          const lyricsVisible = showVideoView ? videoSplitActive : coverSplitActive || showLyrics;
          const coverVisible = !showVideoView && (coverSplitActive || !showLyrics);
          return (
            <>
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  right: 0,
                  width: splitActive ? lyricsPct : "100%",
                  opacity: showVideoView
                    ? videoSplitActive
                      ? 1
                      : 0
                    : coverSplitActive
                      ? 1
                      : showLyrics
                        ? 1
                        : 0,
                  transition: paneTransition,
                  pointerEvents: showVideoView
                    ? videoSplitActive
                      ? "all"
                      : "none"
                    : coverSplitActive || showLyrics
                      ? "all"
                      : "none",
                }}
              >
                <LyricsOverlay
                  track={currentTrack}
                  audioRef={audioRef}
                  onClose={() => setOverlayOpen(false)}
                  fontSize={lyricsFontSize}
                  providers={lyricsProviders}
                  refetchKey={lyricsRefetchKey}
                  onAddToast={addToast}
                  language={language}
                  forcedProvider={forcedLyricsProvider}
                  onSourceChange={setCurrentLyricsSource}
                  onProviderFailed={(id) => setFailedLyricsProviders((s) => new Set([...s, id]))}
                  showTranslation={showLyricsTranslation}
                  translationLang={lyricsTranslationLang}
                  translationFontSize={lyricsTranslationFontSize}
                  showRomaji={showRomaji}
                  romajiFontSize={lyricsRomajiFontSize}
                  onCustomLyricsStatusChange={setIsCustomLyrics}
                  importLyricsRef={importLyricsRef}
                  removeCustomLyricsRef={removeCustomLyricsRef}
                  openLyricsBrowserRef={openLyricsBrowserRef}
                  showAgentTags={showAgentTags}
                  ambientVisualizer={ambientVisualizer}
                  syllableZoom={syllableZoom}
                  fluidLyrics={fluidLyrics}
                  ambientBackground={ambientBackground}
                  fullscreen={fullscreen}
                  playerBarVisible={playerVisible}
                  onInstrumentalChange={handleInstrumentalChange}
                  isActive={overlayOpen && lyricsVisible}
                  isPlaying={isPlaying}
                />
              </div>
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  left: 0,
                  width: coverSplitActive ? coverPct : "100%",
                  opacity: showVideoView ? 0 : coverSplitActive ? 1 : showLyrics ? 0 : 1,
                  transition: paneTransition,
                  pointerEvents: showVideoView
                    ? "none"
                    : coverSplitActive || !showLyrics
                      ? "all"
                      : "none",
                  borderRight: coverSplitActive ? "1px solid rgba(255,255,255,0.08)" : "none",
                }}
              >
                <CoverView
                  track={currentTrack}
                  isPlaying={isPlaying}
                  onClose={() => setOverlayOpen(false)}
                  ambientVisualizer={ambientVisualizer}
                  vizConfig={vizConfig}
                  narrow={coverSplitActive}
                  isActive={overlayOpen && coverVisible}
                  ambientBackground={ambientBackground}
                />
              </div>
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  left: 0,
                  width: videoSplitActive ? coverPct : "100%",
                  opacity: showVideoView ? 1 : 0,
                  transition: paneTransition,
                  pointerEvents: showVideoView ? "all" : "none",
                }}
              >
                {showVideoView && (
                  <VideoSyncView
                    videoSync={videoSync}
                    audioRef={audioRef}
                    isPlaying={isPlaying}
                    fullscreen={fullscreen}
                    track={currentTrack}
                    showCaptions={videoCaptionsActive}
                    fluidCaptions={fluidLyrics}
                    captionsTranslation={showLyricsTranslation}
                    captionsTranslationLang={lyricsTranslationLang}
                    captionsRomaji={showRomaji}
                    captionsSyllableZoom={syllableZoom}
                  />
                )}
              </div>
              {/* Drag handle between the two panes (mirrors the sidebar/queue handles) */}
              {splitActive && (
                <div
                  onMouseDown={startSplitResize}
                  style={{
                    position: "absolute",
                    top: 0,
                    bottom: 0,
                    left: coverPct,
                    width: 12,
                    marginLeft: -6,
                    cursor: "ew-resize",
                    zIndex: 6,
                  }}
                  onMouseEnter={(e) => {
                    const bar = e.currentTarget.firstChild;
                    if (bar) bar.style.opacity = "1";
                  }}
                  onMouseLeave={(e) => {
                    const bar = e.currentTarget.firstChild;
                    if (bar) bar.style.opacity = splitResizing ? "1" : "0";
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      left: 5,
                      top: 0,
                      bottom: 0,
                      width: 2,
                      background: "rgba(255,255,255,0.55)",
                      opacity: splitResizing ? 1 : 0,
                      transition: "opacity 0.15s",
                      pointerEvents: "none",
                    }}
                  />
                </div>
              )}
            </>
          );
        })()}
    </div>
  );
});
