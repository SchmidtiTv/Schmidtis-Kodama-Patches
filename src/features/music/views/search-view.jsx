import { useEffect, useState } from "react";

import { GridCard, TrackRow } from "@/features/music/components/rows.jsx";
import { API } from "@/shared/api/client.js";
import { thumb } from "@/shared/api/thumbnails.js";
import { useLang } from "@/shared/i18n/context.jsx";
import { LoadingState } from "@/shared/ui/loading-state.jsx";
import { usePlaybackStatus, usePlayerActions } from "../../player/player-context.jsx";
import { shuffleTracks } from "@/features/music/shuffle-tracks.js";

export function SearchView({
  query,
  onOpenArtist,
  onOpenAlbum,
  onOpenPlaylist,
  onContextMenu,
  onTrackContextMenu,
  hideExplicit,
}) {
  const { track: currentTrack, isPlaying } = usePlaybackStatus();
  const { handlePlay } = usePlayerActions();
  const [filter, setFilter] = useState("all");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const t = useLang();

  useEffect(() => {
    if (!query) return;
    setLoading(true);
    setError(null);
    setResults([]);
    fetch(`${API}/search?q=${encodeURIComponent(query)}&filter=${filter}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.error) throw new Error(d.error);
        setResults(d.results || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [query, filter]);

  const tabs = [
    { id: "all", label: t("filterAll") },
    { id: "songs", label: t("filterSongs") },
    { id: "artists", label: t("filterArtists") },
    { id: "albums", label: t("filterAlbums") },
    { id: "playlists", label: t("filterPlaylists") },
  ];

  if (!query)
    return <div style={{ padding: 28, color: "var(--text-secondary)" }}>{t("searchPrompt")}</div>;

  // Backend tags every item with `type`. Filter explicit songs out up front.
  const visible = results.filter((r) => r.type !== "song" || !hideExplicit || !r.isExplicit);
  const byType = (ty) => visible.filter((r) => r.type === ty);
  const gridStyle = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))",
    gap: 16,
    padding: "0 16px",
  };

  const renderSong = (song) => (
    <TrackRow
      key={song.videoId}
      track={song}
      isPlaying={isPlaying && currentTrack?.videoId === song.videoId}
      onPlay={() => handlePlay(song)}
      onOpenArtist={onOpenArtist}
      onContextMenu={onTrackContextMenu}
    />
  );
  const playCollection = async (kind, id, shuffle) => {
    if (!id) return;
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
      // The card remains available for navigation if its collection cannot be loaded.
    }
  };
  const renderArtist = (a, i) => (
    <div
      key={a.browseId || i}
      onClick={() => a.browseId && onOpenArtist?.({ browseId: a.browseId, artist: a.title })}
      style={{
        cursor: a.browseId ? "pointer" : "default",
        borderRadius: "var(--r-lg)",
        padding: "12px 0",
        textAlign: "center",
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.querySelector(".sr-title").style.color = "var(--accent)")
      }
      onMouseLeave={(e) =>
        (e.currentTarget.querySelector(".sr-title").style.color = "var(--text-primary)")
      }
    >
      <div
        style={{
          width: 100,
          height: 100,
          borderRadius: "50%",
          overflow: "hidden",
          background: "var(--bg-elevated)",
          margin: "0 auto 10px",
        }}
      >
        {a.thumbnail ? (
          <img
            src={thumb(a.thumbnail)}
            alt=""
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              background: "var(--placeholder-gradient)",
            }}
          />
        )}
      </div>
      <div
        className="sr-title"
        style={{
          fontSize: "var(--t13)",
          fontWeight: 500,
          transition: "color 0.15s",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {a.title}
      </div>
      {a.subtitle && (
        <div style={{ fontSize: "var(--t11)", color: "var(--text-muted)", marginTop: 3 }}>
          {a.subtitle}
        </div>
      )}
    </div>
  );
  const renderAlbum = (a, i) => (
    <GridCard
      key={a.browseId || i}
      thumbnail={a.thumbnail}
      title={a.title}
      subtitle={`${a.artists}${a.year ? ` · ${a.year}` : ""}`}
      onClick={() =>
        a.browseId &&
        onOpenAlbum?.({ browseId: a.browseId, title: a.title, thumbnail: a.thumbnail })
      }
      onPlay={() => playCollection("album", a.browseId, false)}
      onShuffle={() => playCollection("album", a.browseId, true)}
      playLabel={t("playAll")}
      shuffleLabel={t("shuffle")}
      onContextMenu={
        a.browseId
          ? (e) =>
              onContextMenu?.(e, {
                browseId: a.browseId,
                title: a.title,
                thumbnail: a.thumbnail,
                type: "album",
              })
          : undefined
      }
    />
  );
  const renderPlaylist = (p, i) => {
    const pid = p.playlistId || p.browseId;
    return (
      <GridCard
        key={pid || i}
        thumbnail={p.thumbnail}
        title={p.title}
        subtitle={p.subtitle}
        onClick={() =>
          pid && onOpenPlaylist?.({ playlistId: pid, title: p.title, thumbnail: p.thumbnail })
        }
        onPlay={() => playCollection("playlist", pid, false)}
        onShuffle={() => playCollection("playlist", pid, true)}
        playLabel={t("playAll")}
        shuffleLabel={t("shuffle")}
        onContextMenu={
          pid
            ? (e) =>
                onContextMenu?.(e, {
                  playlistId: pid,
                  browseId: p.browseId,
                  owned: false,
                  title: p.title,
                  thumbnail: p.thumbnail,
                  type: "playlist",
                })
            : undefined
        }
      />
    );
  };

  // A titled section for the mixed "all" view, with a "show all" jump to that tab.
  const section = (label, tabId, node) => (
    <div key={tabId} style={{ marginBottom: 26 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 16px",
          marginBottom: 10,
        }}
      >
        <div style={{ fontSize: "var(--t15)", fontWeight: 600 }}>{label}</div>
        <button
          onClick={() => setFilter(tabId)}
          style={{
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            fontSize: "var(--t12)",
            fontFamily: "var(--font)",
            cursor: "pointer",
            transition: "color 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
        >
          {t("showAll")}
        </button>
      </div>
      {node}
    </div>
  );

  return (
    <div data-testid="view-search" style={{ padding: "20px 12px" }}>
      {/* Header */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: "var(--t18)", fontWeight: 500, marginBottom: 12 }}>
          {t("searchResultsFor")} „{query}"
        </div>
        {/* Filter tabs */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {tabs.map((tab_) => (
            <button
              key={tab_.id}
              onClick={() => setFilter(tab_.id)}
              style={{
                background: filter === tab_.id ? "var(--accent)" : "var(--bg-elevated)",
                color: filter === tab_.id ? "#fff" : "var(--text-secondary)",
                border: "none",
                borderRadius: "var(--r-full)",
                padding: "6px 16px",
                fontSize: "var(--t13)",
                cursor: "pointer",
                fontFamily: "var(--font)",
                transition: "all 0.15s",
              }}
            >
              {tab_.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <LoadingState label={t("loadingDots")} />}
      {error && (
        <div style={{ padding: "0 16px", color: "var(--status-danger)" }}>
          {t("errorLoading")}: {error}
        </div>
      )}
      {!loading && !error && visible.length === 0 && (
        <div style={{ padding: "0 16px", color: "var(--text-muted)" }}>{t("noResults")}</div>
      )}

      {/* Mixed "all" view — a few of each, grouped into sections. */}
      {filter === "all" &&
        !loading &&
        (() => {
          const songs = byType("song"),
            artists = byType("artist"),
            albums = byType("album"),
            playlists = byType("playlist");
          return (
            <>
              {songs.length > 0 &&
                section(t("filterSongs"), "songs", <div>{songs.slice(0, 4).map(renderSong)}</div>)}
              {artists.length > 0 &&
                section(
                  t("filterArtists"),
                  "artists",
                  <div style={gridStyle}>{artists.slice(0, 5).map(renderArtist)}</div>
                )}
              {albums.length > 0 &&
                section(
                  t("filterAlbums"),
                  "albums",
                  <div style={gridStyle}>{albums.slice(0, 5).map(renderAlbum)}</div>
                )}
              {playlists.length > 0 &&
                section(
                  t("filterPlaylists"),
                  "playlists",
                  <div style={gridStyle}>{playlists.slice(0, 5).map(renderPlaylist)}</div>
                )}
            </>
          );
        })()}

      {filter === "songs" && byType("song").map(renderSong)}
      {filter === "artists" && <div style={gridStyle}>{byType("artist").map(renderArtist)}</div>}
      {filter === "albums" && <div style={gridStyle}>{byType("album").map(renderAlbum)}</div>}
      {filter === "playlists" && (
        <div style={gridStyle}>{byType("playlist").map(renderPlaylist)}</div>
      )}
    </div>
  );
}
