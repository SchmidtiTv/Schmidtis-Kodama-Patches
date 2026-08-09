import { useCallback, useEffect, useState } from "react";
import { API } from "@/shared/api/client.js";
import { useLang } from "@/shared/i18n/context.jsx";
import { LoadingState } from "@/shared/ui/loading-state.jsx";
import { PlaylistLayout } from "@/features/music/components/track-table.jsx";
import { SYSTEM_MIX_COLLECTION_IDS } from "@/features/music/mix-collection.js";

const PAGE_SIZE = 50;

export function LikedView({
  onOpenArtist,
  onOpenAlbum,
  onTrackContextMenu,
  hideExplicit,
  onToggleLike,
  likedIds,
  selectedTracks,
  onToggleSelect,
  onSelectAll,
  onBack,
}) {
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [errorCode, setErrorCode] = useState(null);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const t = useLang();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setErrorCode(null);
    fetch(`${API}/liked?offset=0&limit=${PAGE_SIZE}`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d.error) {
          const err = new Error(d.error);
          err.code = d.code;
          throw err;
        }
        setTracks(d.tracks || []);
        setTotal(d.total ?? (d.tracks || []).length);
        setHasMore(Boolean(d.hasMore));
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e.message);
        setErrorCode(e.code || null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadMore = useCallback(() => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    fetch(`${API}/liked?offset=${tracks.length}&limit=${PAGE_SIZE}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.error) throw new Error(d.error);
        setTracks((current) => [...current, ...(d.tracks || [])]);
        setTotal(d.total ?? tracks.length + (d.tracks || []).length);
        setHasMore(Boolean(d.hasMore));
      })
      .catch(() => {})
      .finally(() => setLoadingMore(false));
  }, [hasMore, loadingMore, tracks.length]);

  if (loading)
    return <LoadingState label={t("loadingLikedSongs")} minHeight="100%" />;

  if (error && errorCode === "auth_expired")
    return (
      <div style={{ padding: 28 }}>
        <div style={{ color: "var(--status-danger)", marginBottom: 8 }}>{t("sessionExpired")}</div>
        <div style={{ color: "var(--text-secondary)", fontSize: "var(--t13)" }}>
          {t("sessionExpiredHint")}
        </div>
      </div>
    );

  if (error)
    return (
      <div style={{ padding: 28 }}>
        <div style={{ color: "var(--status-danger)", marginBottom: 8 }}>{t("errorLoading")}</div>
        <div style={{ color: "var(--text-secondary)", fontSize: "var(--t13)" }}>{error}</div>
        <div style={{ color: "var(--text-muted)", fontSize: "var(--t12)", marginTop: 12 }}>
          {t("backendHint")}{" "}
          <code
            style={{
              background: "var(--bg-elevated)",
              padding: "1px 6px",
              borderRadius: "var(--r-sm)",
            }}
          >
            python server.py
          </code>
        </div>
      </div>
    );

  return (
    <div data-testid="view-liked">
      <PlaylistLayout
        title={t("likedSongs")}
        mixCollectionId={SYSTEM_MIX_COLLECTION_IDS.likedSongs}
        thumbnail={null}
        tracks={tracks}
        total={total}
        loading={false}
        progress={0}
        cached={false}
        onBack={onBack || null}
        isLiked={true}
        onOpenArtist={onOpenArtist}
        onOpenAlbum={onOpenAlbum}
        onTrackContextMenu={onTrackContextMenu}
        hideExplicit={hideExplicit}
        onToggleLike={onToggleLike}
        likedIds={likedIds}
        selectedTracks={selectedTracks}
        onToggleSelect={onToggleSelect}
        onSelectAll={onSelectAll}
        hasMore={hasMore}
        loadingMore={loadingMore}
        onLoadMore={loadMore}
      />
    </div>
  );
}
