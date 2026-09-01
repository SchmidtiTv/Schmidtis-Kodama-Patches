import { lazy, memo, Suspense, useLayoutEffect, useMemo, useRef } from "react";
import { ScrollShadowRoot } from "@heroui/react";

import { translate } from "@/shared/i18n/i18n.js";
import { WifiX } from "@/shared/icons/icons.jsx";
import { LoadingState } from "@/shared/ui/loading-state.jsx";

const CollectionView = lazy(() =>
  import("@/features/music/views/collection-view.jsx").then(({ CollectionView: Component }) => ({
    default: Component,
  }))
);
const DownloadsView = lazy(() =>
  import("@/features/downloads/downloads-view.jsx").then(({ DownloadsView: Component }) => ({
    default: Component,
  }))
);
const HistoryView = lazy(() =>
  import("@/features/music/views/history-view.jsx").then(({ HistoryView: Component }) => ({
    default: Component,
  }))
);
const LikedView = lazy(() =>
  import("@/features/music/views/liked-view.jsx").then(({ LikedView: Component }) => ({
    default: Component,
  }))
);
const LibraryView = lazy(() =>
  import("@/features/music/views/library-view.jsx").then(({ LibraryView: Component }) => ({
    default: Component,
  }))
);
const SearchView = lazy(() =>
  import("@/features/music/views/search-view.jsx").then(({ SearchView: Component }) => ({
    default: Component,
  }))
);
const HomeView = lazy(() =>
  import("@/features/music/views/home-view.jsx").then(({ HomeView: Component }) => ({
    default: Component,
  }))
);
const ArtistView = lazy(() =>
  import("@/features/music/views/artist-view.jsx").then(({ ArtistView: Component }) => ({
    default: Component,
  }))
);

// "backwards" rather than "both": filling forwards keeps the animation applied for good, and
// an element with an applied transform animation stays promoted to its own compositing layer
// even at the identity matrix — on a wrapper that spans a whole playlist view that is a very
// large layer. The end state is the natural one anyway, so nothing needs holding; "backwards"
// still covers the flash before the animation starts.
function AnimatedView({ animations, children }) {
  return (
    <div
      style={{
        animation: animations ? "fadeSlideIn 0.28s cubic-bezier(0.22,1,0.36,1) backwards" : "none",
      }}
    >
      {children}
    </div>
  );
}

function OfflineBanner({ language }) {
  return (
    <div
      style={{
        position: "sticky",
        bottom: 0,
        left: 0,
        right: 0,
        background: "var(--status-warning-soft)",
        borderTop: "1px solid var(--status-warning-line)",
        color: "var(--status-warning)",
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 16px",
        fontSize: 13,
        zIndex: 10,
      }}
    >
      <WifiX size={15} weight="bold" />
      {translate(language, "offlineBanner")}
    </div>
  );
}

export const MainContent = memo(function MainContent({
  appKey,
  view,
  viewRefreshKey,
  animations,
  profiles,
  openPlaylist,
  openAlbum,
  openArtist,
  openContextMenu,
  setTrackContextMenu,
  hideExplicit,
  searchQuery,
  handleToggleLike,
  likedIds,
  selectedTracks,
  toggleTrackSelection,
  selectAllTracks,
  goBack,
  collection,
  artistView,
  togglePin,
  pinnedIds,
  isOffline,
  language,
}) {
  const activeProfileKey = profiles.find((profile) => profile.active)?.name || "default";
  const activeDisplayName = profiles.find((profile) => profile.active)?.displayName;
  const loadingFallback = <LoadingState label={translate(language, "loadingDots")} />;
  const homeActionsRef = useRef({
    openAlbum,
    openArtist,
    openContextMenu,
    openPlaylist,
    setTrackContextMenu,
  });
  useLayoutEffect(() => {
    homeActionsRef.current = {
      openAlbum,
      openArtist,
      openContextMenu,
      openPlaylist,
      setTrackContextMenu,
    };
  }, [openAlbum, openArtist, openContextMenu, openPlaylist, setTrackContextMenu]);
  const homeView = useMemo(
    () => (
      <HomeView
        displayName={activeDisplayName}
        onOpenPlaylist={(item) => homeActionsRef.current.openPlaylist(item, "home")}
        onOpenAlbum={(item) => homeActionsRef.current.openAlbum(item, "home")}
        onOpenArtist={(item) => homeActionsRef.current.openArtist(item, "home")}
        onContextMenu={(...args) => homeActionsRef.current.openContextMenu(...args)}
        onTrackContextMenu={(e, track) =>
          homeActionsRef.current.setTrackContextMenu({ x: e.clientX, y: e.clientY, track })
        }
        hideExplicit={hideExplicit}
        profileKey={activeProfileKey}
        refreshKey={viewRefreshKey}
      />
    ),
    [activeDisplayName, activeProfileKey, hideExplicit, viewRefreshKey]
  );

  return (
    <div style={{ position: "relative", height: "100%" }}>
      <ScrollShadowRoot
        key={`home-${appKey}`}
        aria-hidden={view !== "home"}
        inert={view !== "home"}
        size={28}
        className="scrollable overflow-y-auto"
        style={{
          position: "absolute",
          inset: 0,
          zIndex: view === "home" ? 1 : 0,
          opacity: view === "home" ? 1 : 0,
          pointerEvents: view === "home" ? "auto" : "none",
          willChange: "opacity",
        }}
      >
        <AnimatedView key={`home-${activeProfileKey}-${viewRefreshKey}`} animations={animations}>
          <Suspense fallback={loadingFallback}>{homeView}</Suspense>
        </AnimatedView>
        {isOffline && <OfflineBanner language={language} />}
        <div style={{ height: 97, flexShrink: 0, pointerEvents: "none" }} aria-hidden="true" />
      </ScrollShadowRoot>
      <ScrollShadowRoot
        key={appKey}
        aria-hidden={view === "home"}
        size={28}
        className="scrollable overflow-y-auto"
        style={{
          position: "absolute",
          inset: 0,
          visibility: view === "home" ? "hidden" : "visible",
          pointerEvents: view === "home" ? "none" : "auto",
        }}
      >
        {view === "search" && (
          <AnimatedView key={`search-${viewRefreshKey}`} animations={animations}>
            <Suspense fallback={loadingFallback}>
              <SearchView
                query={searchQuery}
                onOpenArtist={openArtist}
                onOpenAlbum={(item) => openAlbum(item, "search")}
                onOpenPlaylist={(item) => openPlaylist(item, "search")}
                onContextMenu={openContextMenu}
                onTrackContextMenu={(e, track) =>
                  setTrackContextMenu({ x: e.clientX, y: e.clientY, track })
                }
                hideExplicit={hideExplicit}
              />
            </Suspense>
          </AnimatedView>
        )}
        {view === "liked" && (
          <AnimatedView key={`liked-${viewRefreshKey}`} animations={animations}>
            <Suspense fallback={loadingFallback}>
              <LikedView
                onOpenArtist={openArtist}
                onOpenAlbum={(item) => openAlbum(item, "liked")}
                onTrackContextMenu={(e, track) =>
                  setTrackContextMenu({ x: e.clientX, y: e.clientY, track })
                }
                hideExplicit={hideExplicit}
                onToggleLike={handleToggleLike}
                likedIds={likedIds}
                selectedTracks={selectedTracks}
                onToggleSelect={toggleTrackSelection}
                onSelectAll={selectAllTracks}
                onBack={goBack}
              />
            </Suspense>
          </AnimatedView>
        )}
        {view === "history" && (
          <AnimatedView key={`history-${viewRefreshKey}`} animations={animations}>
            <Suspense fallback={loadingFallback}>
              <HistoryView
                onOpenArtist={openArtist}
                onOpenAlbum={(item) => openAlbum(item, "history")}
                onTrackContextMenu={(e, track, extra) =>
                  setTrackContextMenu({
                    x: e.clientX,
                    y: e.clientY,
                    track,
                    ...extra,
                  })
                }
                hideExplicit={hideExplicit}
              />
            </Suspense>
          </AnimatedView>
        )}
        {view === "library" && (
          <AnimatedView key={`library-${viewRefreshKey}`} animations={animations}>
            <Suspense fallback={loadingFallback}>
              <LibraryView
                onOpenPlaylist={openPlaylist}
                onOpenAlbum={openAlbum}
                onOpenArtist={openArtist}
                onContextMenu={openContextMenu}
              />
            </Suspense>
          </AnimatedView>
        )}
        {view === "collection" && collection && (
          <AnimatedView key={`collection-${viewRefreshKey}`} animations={animations}>
            <Suspense fallback={loadingFallback}>
              <CollectionView
                title={collection.title}
                description={collection.description}
                thumbnail={collection.thumbnail}
                playlistId={collection.playlistId}
                browseId={collection.browseId}
                tracks={collection.tracks}
                total={collection.total}
                loading={collection.loading}
                progress={collection.progress || 0}
                cached={collection.cached}
                onBack={goBack}
                onOpenArtist={openArtist}
                onOpenAlbum={(item) => openAlbum(item, "collection")}
                isAlbum={collection.isAlbum}
                albumArtists={collection.albumArtists}
                albumArtistBrowseId={collection.albumArtistBrowseId}
                year={collection.year}
                onRefresh={() => {
                  if (collection.isAlbum)
                    openAlbum(
                      {
                        browseId: collection.browseId,
                        title: collection.title,
                        thumbnail: collection.thumbnail,
                      },
                      collection.fromView,
                      true
                    );
                  else
                    openPlaylist(
                      {
                        playlistId: collection.playlistId,
                        title: collection.title,
                        thumbnail: collection.thumbnail,
                        forcedTitle: collection.forcedTitle,
                      },
                      collection.fromView,
                      true
                    );
                }}
                onTrackContextMenu={(e, track) =>
                  setTrackContextMenu({
                    x: e.clientX,
                    y: e.clientY,
                    track,
                    playlistId: collection.isAlbum ? null : collection.playlistId,
                  })
                }
                hideExplicit={hideExplicit}
                onToggleLike={handleToggleLike}
                likedIds={likedIds}
                selectedTracks={selectedTracks}
                onToggleSelect={toggleTrackSelection}
                onSelectAll={selectAllTracks}
                onCollectionActions={openContextMenu}
              />
            </Suspense>
          </AnimatedView>
        )}
        {view === "artist" && artistView && (
          <AnimatedView key={`artist-${viewRefreshKey}`} animations={animations}>
            <Suspense fallback={loadingFallback}>
              <ArtistView
                browseId={artistView.browseId}
                onOpenAlbum={(item) => openAlbum(item, "artist")}
                onOpenPlaylist={(item) => openPlaylist(item, "artist")}
                onOpenArtist={(item) => openArtist(item, "artist")}
                onBack={goBack}
                onContextMenu={openContextMenu}
                onTogglePin={togglePin}
                isPinned={pinnedIds.includes(artistView.browseId)}
                hideExplicit={hideExplicit}
              />
            </Suspense>
          </AnimatedView>
        )}
        {view === "downloads" && (
          <AnimatedView key={`downloads-${viewRefreshKey}`} animations={animations}>
            <Suspense fallback={loadingFallback}>
              <DownloadsView
                onTrackContextMenu={(e, track) =>
                  setTrackContextMenu({ x: e.clientX, y: e.clientY, track })
                }
                hideExplicit={hideExplicit}
                onOpenAlbum={(item) => openAlbum(item, "downloads")}
                onOpenArtist={openArtist}
                onToggleLike={handleToggleLike}
                likedIds={likedIds}
              />
            </Suspense>
          </AnimatedView>
        )}
        {isOffline && view !== "downloads" && <OfflineBanner language={language} />}
        {/* Spacer so content scrolls clear of the floating player bar */}
        <div style={{ height: 97, flexShrink: 0, pointerEvents: "none" }} aria-hidden="true" />
      </ScrollShadowRoot>
    </div>
  );
});
