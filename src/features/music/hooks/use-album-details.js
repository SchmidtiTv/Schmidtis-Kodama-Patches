import { useEffect, useState } from "react";
import { API } from "@/shared/api/client.js";

/**
 * Looks up canonical release details (record label, MusicBrainz release id) for
 * an album via the backend's MusicBrainz-backed lookup. This is enrichment on
 * top of the YouTube Music album data, not core data, so callers should treat
 * `null` as "nothing to show" rather than a loading state.
 */
export function useAlbumDetails({ enabled, browseId, artist, album }) {
  // Keyed by the params it was fetched for, so a stale response from a previous
  // album can't flash on screen while the next album's lookup is still in flight.
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!enabled || !browseId || !artist || !album) return undefined;

    const controller = new AbortController();
    const query = new URLSearchParams({ artist, album });
    fetch(`${API}/album/${encodeURIComponent(browseId)}/musicbrainz?${query}`, {
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!controller.signal.aborted) {
          setResult(data && !data.error ? { browseId, artist, album, details: data } : null);
        }
      })
      .catch((error) => {
        if (error.name !== "AbortError") setResult(null);
      });

    return () => controller.abort();
  }, [enabled, browseId, artist, album]);

  const isCurrent =
    enabled &&
    result?.browseId === browseId &&
    result?.artist === artist &&
    result?.album === album;
  return isCurrent ? result.details : null;
}
