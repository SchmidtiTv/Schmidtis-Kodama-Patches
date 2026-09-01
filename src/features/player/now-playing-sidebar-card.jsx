import { useState } from "react";
import { Button } from "@heroui/react";
import { Heart } from "@/shared/icons/icons.jsx";
import { thumbHi } from "@/shared/api/thumbnails.js";
import { RetryingImage } from "@/shared/ui/retrying-image.jsx";
import { useSongCanvasArtwork } from "./use-song-canvas-artwork.js";

function artistNames(artists) {
  if (Array.isArray(artists)) {
    return artists
      .map((artist) => (typeof artist === "string" ? artist : artist?.name || artist?.artist))
      .filter(Boolean)
      .join(", ");
  }
  return artists || "";
}

export function NowPlayingSidebarCard({
  track,
  contextTitle,
  isLiked,
  onToggleLike,
  saveLabel,
  canvasEnabled,
  canvasSource,
  className = "",
}) {
  const canvasArtwork = useSongCanvasArtwork(track, {
    enabled: canvasEnabled,
    source: canvasSource,
  });
  const [readyCanvasUrl, setReadyCanvasUrl] = useState("");

  if (!track) return null;

  const artists = artistNames(track.artists);
  const artwork = track.thumbnail ? thumbHi(track.thumbnail, 720) : "";

  return (
    <section className={`spotify-now-playing ${className}`} aria-label={contextTitle}>
      {artwork ? (
        <RetryingImage
          src={artwork}
          alt=""
          loading="eager"
          className="spotify-now-playing__artwork"
        />
      ) : (
        <div className="spotify-now-playing__artwork spotify-now-playing__artwork--empty" />
      )}
      {canvasArtwork?.url && (
        <video
          key={canvasArtwork.url}
          src={canvasArtwork.url}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden="true"
          className={`spotify-now-playing__canvas ${readyCanvasUrl === canvasArtwork.url ? "is-ready" : ""}`}
          onCanPlay={() => setReadyCanvasUrl(canvasArtwork.url)}
          onError={() => setReadyCanvasUrl((currentUrl) => (currentUrl === canvasArtwork.url ? "" : currentUrl))}
        />
      )}

      <div className="spotify-now-playing__shade" aria-hidden="true" />
      <h2 className="spotify-now-playing__context">{contextTitle}</h2>

      <div className="spotify-now-playing__footer">
        <div className="spotify-now-playing__metadata">
          <div className="spotify-now-playing__title">{track.title || "—"}</div>
          {artists && <div className="spotify-now-playing__artist">{artists}</div>}
        </div>

        <div className="spotify-now-playing__actions">
          <Button
            isIconOnly
            variant="light"
            onPress={() => onToggleLike?.(track)}
            aria-label={saveLabel}
            title={saveLabel}
            className="spotify-now-playing__save"
            data-liked={isLiked ? "true" : undefined}
          >
            <Heart size={19} weight={isLiked ? "fill" : "regular"} />
          </Button>
        </div>
      </div>
    </section>
  );
}
