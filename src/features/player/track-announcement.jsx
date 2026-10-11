import { useEffect, useState } from "react";
import { useLang } from "@/shared/i18n/context.jsx";
export function TrackAnnouncement({ enabled, track }) {
  const t = useLang();
  const [text, setText] = useState("");
  const title = track?.title || "";
  const artist = Array.isArray(track?.artists)
    ? track.artists.map((value) => value?.name || value).join(", ")
    : track?.artists || "";
  useEffect(() => {
    const clear = setTimeout(() => setText(""), 0);
    const announce = setTimeout(() => {
      if (enabled && title)
        setText(t(artist ? "announceNowPlaying" : "announceNowPlayingNoArtist", { title, artist }));
    }, 150);
    return () => {
      clearTimeout(clear);
      clearTimeout(announce);
    };
  }, [enabled, track?.videoId, title, artist, t]);
  return (
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {text}
    </div>
  );
}
