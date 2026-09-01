import { useEffect, useState } from "react";

import { API } from "@/shared/api/client.js";

function artistName(artists) {
  if (Array.isArray(artists)) {
    return artists
      .map((artist) => (typeof artist === "string" ? artist : artist?.name || artist?.artist || ""))
      .filter(Boolean)
      .join(", ");
  }
  return typeof artists === "string" ? artists : "";
}

function durationSeconds(track) {
  if (Number.isFinite(track?.durationSeconds)) return track.durationSeconds;
  if (Number.isFinite(track?.duration)) return track.duration;
  const parts = typeof track?.duration === "string" ? track.duration.split(":").map(Number) : [];
  if (parts.length === 2 && parts.every(Number.isFinite)) return parts[0] * 60 + parts[1];
  if (parts.length === 3 && parts.every(Number.isFinite)) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return undefined;
}

export function useSongCanvasArtwork(track, { enabled = true, source = "auto" } = {}) {
  const [resolved, setResolved] = useState({ key: "", artwork: null });
  const videoId = track?.videoId;
  const title = track?.title || "";
  const artist = artistName(track?.artists);
  const album = typeof track?.album === "string" ? track.album : track?.album?.name || "";
  const duration = durationSeconds(track);
  const requestKey = [videoId, title, artist, album, duration, enabled, source].join("\u001f");

  useEffect(() => {
    if (!enabled || !videoId || !title || !artist) return undefined;
    const controller = new AbortController();
    fetch(`${API}/song/canvas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({ title, artist, album, durationSeconds: duration, source }),
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((result) => {
        if (!controller.signal.aborted) {
          setResolved({ key: requestKey, artwork: typeof result?.url === "string" ? result : null });
        }
      })
      .catch(() => {});
    return () => controller.abort();
  }, [album, artist, duration, enabled, requestKey, source, title, videoId]);

  return resolved.key === requestKey ? resolved.artwork : null;
}
