import { useEffect, useRef, useState } from "react";
import { Tab, TabIndicator, TabList, TabListContainer, TabsRoot } from "@heroui/react";
import { SharedElementTransition } from "react-aria-components";

import { GridCard } from "@/features/music/components/rows.jsx";
import {
  MagnifyingGlass,
  Microphone,
  Playlist,
  Sliders,
  VinylRecord,
  WarningCircle,
} from "@/shared/icons/icons.jsx";
import { API } from "@/shared/api/client.js";
import { useLang } from "@/shared/i18n/context.jsx";
import { LoadingState } from "@/shared/ui/loading-state.jsx";
import { usePlayerActions } from "@/features/player/player-context.jsx";
import { shuffleTracks } from "@/features/music/shuffle-tracks.js";
import { useProfileState, useProfileActions } from "@/features/profiles/profile-context.jsx";

export function LibraryView({ onOpenPlaylist, onOpenAlbum, onOpenArtist, onContextMenu }) {
  const [tab, setTab] = useState("playlists");
  const [playlists, setPlaylists] = useState([]);
  const [albums, setAlbums] = useState([]);
  const [artists, setArtists] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [sortOrder, setSortOrder] = useState("default");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef(null);
  const t = useLang();
  const { handlePlay } = usePlayerActions();
  const { sessionExpired, activeProfile } = useProfileState();
  const { reauthProfile } = useProfileActions();

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus();
  }, [searchOpen]);
  useEffect(() => {
    setSearchQuery("");
    setSearchOpen(false);
  }, [tab]);

  useEffect(() => {
    const handler = () => setRefreshKey((k) => k + 1);
    window.addEventListener("kiyoshi-library-updated", handler);
    return () => window.removeEventListener("kiyoshi-library-updated", handler);
  }, []);

  // Targeted, refetch-free removal of a single playlist (used when deleting): drops just that
  // card from the local list so the grid doesn't reload and flash empty.
  useEffect(() => {
    const onRemoved = (e) => setPlaylists((prev) => prev.filter((p) => p.playlistId !== e.detail));
    window.addEventListener("kiyoshi-playlist-removed", onRemoved);
    return () => window.removeEventListener("kiyoshi-playlist-removed", onRemoved);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const endpoints = {
      playlists: `${API}/library/playlists`,
      albums: `${API}/library/albums`,
      artists: `${API}/library/artists`,
    };
    fetch(endpoints[tab])
      .then((r) => r.json())
      .then((d) => {
        if (d.error) throw new Error(d.error);
        if (tab === "playlists") setPlaylists(d.playlists || []);
        if (tab === "albums") setAlbums(d.albums || []);
        if (tab === "artists") setArtists(d.artists || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tab, refreshKey]);

  const tabs = [
    { id: "playlists", label: t("filterPlaylists"), icon: <Playlist size={14} /> },
    { id: "albums", label: t("filterAlbums"), icon: <VinylRecord size={14} /> },
    { id: "artists", label: t("filterArtists"), icon: <Microphone size={14} /> },
  ];

  const rawItems = tab === "playlists" ? playlists : tab === "albums" ? albums : artists;

  const items = [...rawItems]
    .sort((a, b) => {
      const nameA = (tab === "artists" ? a.artist : a.title) || "";
      const nameB = (tab === "artists" ? b.artist : b.title) || "";
      if (sortOrder === "az") return nameA.localeCompare(nameB);
      if (sortOrder === "za") return nameB.localeCompare(nameA);
      if (sortOrder === "artist") return (a.artists || "").localeCompare(b.artists || "");
      if (sortOrder === "year_desc") return (parseInt(b.year) || 0) - (parseInt(a.year) || 0);
      if (sortOrder === "year_asc") return (parseInt(a.year) || 0) - (parseInt(b.year) || 0);
      return 0; // "default" — keep API order
    })
    .filter((item) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      if (tab === "artists") return (item.artist || "").toLowerCase().includes(q);
      return (
        (item.title || "").toLowerCase().includes(q) ||
        (item.artists || "").toLowerCase().includes(q)
      );
    });

  const playCollection = async (kind, id, shuffle) => {
    const endpoint = kind === "album" ? `${API}/album/${id}` : `${API}/playlist/${id}`;
    try {
      const response = await fetch(endpoint);
      if (!response.ok) return;
      const payload = await response.json();
      const tracks = (payload.tracks || []).filter((track) => track.videoId);
      if (!tracks.length) return;
      const queue = shuffle ? shuffleTracks(tracks) : tracks;
      handlePlay(queue[0], queue);
    } catch {
      // Opening the card remains available if the quick action cannot load the collection.
    }
  };

  const sortOptions = [
    { value: "default", label: t("sortDefault") },
    { value: "az", label: t("sortAlphaAZ") },
    { value: "za", label: t("sortAlphaZA") },
    ...(tab === "albums"
      ? [
          { value: "artist", label: t("sortByArtist") },
          { value: "year_desc", label: t("sortByYearDesc") },
          { value: "year_asc", label: t("sortByYearAsc") },
        ]
      : []),
  ];

  return (
    <div data-testid="view-library" style={{ padding: "24px 24px 0" }}>
      {/* Header row: title left, tabs centered */}
      <div
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          marginBottom: 12,
          height: 36,
        }}
      >
        <div style={{ fontSize: "var(--t22)", fontWeight: 600 }}>{t("library")}</div>
        <div style={{ position: "absolute", left: "50%", transform: "translateX(-50%)" }}>
          <SharedElementTransition>
            <TabsRoot
              selectedKey={tab}
              onSelectionChange={(key) => {
                setTab(key);
                setSortOrder("default");
              }}
            >
              <TabListContainer>
                <TabList aria-label={t("library")}>
                  {tabs.map((tab_) => (
                    <Tab key={tab_.id} id={tab_.id} className="gap-1.5">
                      {tab_.icon}
                      {tab_.label}
                    </Tab>
                  ))}
                </TabList>
                <TabIndicator />
              </TabListContainer>
            </TabsRoot>
          </SharedElementTransition>
        </div>
      </div>

      {/* Sort + search row */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 20 }}>
        <Sliders size={12} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
        {sortOptions.map((o) => (
          <button
            key={o.value}
            onClick={() => setSortOrder(o.value)}
            style={{
              background:
                sortOrder === o.value
                  ? "color-mix(in srgb, var(--accent) 15%, transparent)"
                  : "none",
              border: "none",
              borderRadius: "var(--r-md)",
              padding: "3px 9px",
              fontSize: "var(--t12)",
              fontFamily: "var(--font)",
              color: sortOrder === o.value ? "var(--accent)" : "var(--text-muted)",
              fontWeight: sortOrder === o.value ? 600 : 400,
              cursor: "default",
              transition: "all 0.15s",
            }}
            onMouseEnter={(e) => {
              if (sortOrder !== o.value) e.currentTarget.style.color = "var(--text-secondary)";
            }}
            onMouseLeave={(e) => {
              if (sortOrder !== o.value) e.currentTarget.style.color = "var(--text-muted)";
            }}
          >
            {o.label}
          </button>
        ))}
        {/* Search — right side */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              width: searchOpen ? 200 : 0,
              overflow: "hidden",
              transition: "width 0.25s cubic-bezier(0.4,0,0.2,1)",
            }}
          >
            <input
              ref={searchRef}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  setSearchQuery("");
                  setSearchOpen(false);
                }
              }}
              placeholder={t("search")}
              style={{
                background: "var(--bg-elevated)",
                border: "0.5px solid var(--border)",
                borderRadius: "var(--r-full)",
                padding: "5px 12px",
                fontSize: "var(--t12)",
                color: "var(--text-primary)",
                outline: "none",
                width: 200,
                fontFamily: "var(--font)",
              }}
            />
          </div>
          <button
            onClick={() => {
              setSearchOpen((v) => !v);
              if (searchOpen) setSearchQuery("");
            }}
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              flexShrink: 0,
              background: searchOpen
                ? "color-mix(in srgb, var(--accent) 18%, transparent)"
                : "var(--bg-elevated)",
              border: "0.5px solid var(--border)",
              color: searchOpen ? "var(--accent)" : "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "default",
              transition: "all 0.15s",
              padding: 0,
            }}
            onMouseEnter={(e) => {
              if (!searchOpen) e.currentTarget.style.color = "var(--text-primary)";
            }}
            onMouseLeave={(e) => {
              if (!searchOpen) e.currentTarget.style.color = "var(--text-secondary)";
            }}
          >
            <MagnifyingGlass size={13} />
          </button>
        </div>
      </div>

      {loading && <LoadingState label={t("loadingDots")} />}
      {error && <div style={{ color: "var(--status-danger)" }}>{error}</div>}
      {/* An empty library used to render an empty grid and nothing else — which is exactly what
          an expired session looks like too, since the request comes back with nothing. Say
          which of the two it is instead of leaving the user to guess. */}
      {!loading && !error && items.length === 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 10,
            padding: "48px 24px",
            textAlign: "center",
            color: "var(--text-secondary)",
          }}
        >
          {sessionExpired ? (
            <>
              <WarningCircle size={26} weight="fill" style={{ color: "var(--status-warning)" }} />
              <div style={{ color: "var(--text-primary)", fontWeight: 600 }}>
                {t("sessionExpired")}
              </div>
              <div style={{ maxWidth: 420 }}>{t("sessionExpiredHint")}</div>
              {activeProfile && (
                <button
                  onClick={() => reauthProfile(activeProfile.name)}
                  style={{
                    marginTop: 6,
                    background: "var(--bg-elevated)",
                    border: "0.5px solid var(--border)",
                    borderRadius: "var(--r-md)",
                    padding: "6px 14px",
                    fontSize: "var(--t13)",
                    fontFamily: "var(--font)",
                    color: "var(--text-primary)",
                    cursor: "default",
                  }}
                >
                  {t("reauthSession")}
                </button>
              )}
            </>
          ) : (
            <div>{t(searchQuery ? "noResults" : "libraryEmpty")}</div>
          )}
        </div>
      )}
      {!loading && !error && items.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))",
            gap: 16,
          }}
        >
          {items.map((item, i) => {
            if (tab === "playlists")
              return (
                <GridCard
                  key={item.playlistId || i}
                  cardId={item.playlistId}
                  thumbnail={item.thumbnail}
                  title={item.title}
                  count={item.count || undefined}
                  onClick={() => onOpenPlaylist(item)}
                  onPlay={() => playCollection("playlist", item.playlistId, false)}
                  onShuffle={() => playCollection("playlist", item.playlistId, true)}
                  playLabel={t("playAll")}
                  shuffleLabel={t("shuffle")}
                  onContextMenu={onContextMenu ? (e) => onContextMenu(e, item) : undefined}
                />
              );
            if (tab === "albums")
              return (
                <GridCard
                  key={item.browseId || item.playlistId || i}
                  thumbnail={item.thumbnail}
                  title={item.title}
                  subtitle={`${item.artists}${item.year ? ` · ${item.year}` : ""}`}
                  onClick={() => onOpenAlbum(item)}
                  onPlay={() => playCollection("album", item.browseId, false)}
                  onShuffle={() => playCollection("album", item.browseId, true)}
                  playLabel={t("playAll")}
                  shuffleLabel={t("shuffle")}
                  onContextMenu={
                    onContextMenu ? (e) => onContextMenu(e, { ...item, type: "album" }) : undefined
                  }
                />
              );
            if (tab === "artists")
              return (
                <GridCard
                  key={item.browseId || i}
                  thumbnail={item.thumbnail}
                  title={item.artist}
                  count={item.songs || undefined}
                  onClick={() => onOpenArtist(item)}
                  onContextMenu={
                    onContextMenu
                      ? (e) => onContextMenu(e, { ...item, title: item.artist, type: "artist" })
                      : undefined
                  }
                />
              );
          })}
        </div>
      )}
    </div>
  );
}
