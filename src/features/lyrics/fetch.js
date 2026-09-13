import { API } from "@/shared/api/client.js";
import { DEFAULT_LYRICS_PROVIDERS, lyricsSyncQuality } from "./providers.js";
import { parseLrc, parseNetease, parseQrc, parseRichSync, parseTtml } from "./parse.js";

async function fetchLyrics(
  title,
  artist,
  album,
  duration,
  providers = DEFAULT_LYRICS_PROVIDERS,
  videoId = "",
  signal = undefined,
  onUpdate = null
) {
  const opt = signal ? { signal } : undefined; // AbortSignal so a track change can cancel in-flight
  const tryBetter = async () => {
    const params = new URLSearchParams({ title, artist, source: "better" });
    if (album) params.set("album", album);
    if (duration) params.set("duration", Math.round(duration));
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (r.ok) {
      const d = await r.json();
      if (d?.ttml) {
        const lrc = parseTtml(d.ttml);
        if (lrc.length) return { source: "Better Lyrics", lrc };
      }
    }
    return null;
  };
  const tryUnison = async () => {
    const params = new URLSearchParams({ title, artist, source: "unison" });
    if (album) params.set("album", album);
    if (duration) params.set("duration", Math.round(duration));
    if (videoId) params.set("videoId", videoId);
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (r.ok) {
      const d = await r.json();
      const sub = d?.submitterName || null;
      if (d?.ttml) {
        const lrc = parseTtml(d.ttml);
        if (lrc.length) return { source: "Unison", lrc, submitterName: sub };
      }
      if (d?.synced) return { source: "Unison", lrc: parseLrc(d.synced), submitterName: sub };
      if (d?.plain)
        return {
          source: "Unison",
          lrc: d.plain.split("\n").map((t) => ({ time: -1, text: t })),
          submitterName: sub,
        };
    }
    return null;
  };
  const tryBiniLyrics = async () => {
    const params = new URLSearchParams({ title, artist, source: "binilyrics" });
    if (album) params.set("album", album);
    if (duration) params.set("duration", Math.round(duration));
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (r.ok) {
      const d = await r.json();
      if (d?.ttml) {
        const lrc = parseTtml(d.ttml);
        if (lrc.length) return { source: "BiniLyrics", lrc };
      }
    }
    return null;
  };
  const tryLrclib = async () => {
    const params = new URLSearchParams({ title, artist, source: "lrclib" });
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (r.ok) {
      const d = await r.json();
      if (d.synced) return { source: "LRCLIB", lrc: parseLrc(d.synced) };
      if (d.plain)
        return { source: "LRCLIB", lrc: d.plain.split("\n").map((t) => ({ time: -1, text: t })) };
    }
    return null;
  };
  const tryKugou = async () => {
    const params = new URLSearchParams({ title, artist, source: "kugou" });
    if (duration) params.set("duration", Math.round(duration));
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (r.ok) {
      const d = await r.json();
      if (d.synced) return { source: "Kugou", lrc: parseLrc(d.synced, { title, artist }) };
    }
    return null;
  };
  const trySimp = async () => {
    const params = new URLSearchParams({ title, artist, source: "simp" });
    if (videoId) params.set("videoId", videoId);
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (r.ok) {
      const d = await r.json();
      if (d.synced) return { source: "SimpMusic", lrc: parseLrc(d.synced) };
      if (d.plain)
        return {
          source: "SimpMusic",
          lrc: d.plain.split("\n").map((t) => ({ time: -1, text: t })),
        };
    }
    return null;
  };
  const tryYoutube = async () => {
    if (!videoId) return null;
    const params = new URLSearchParams({ title, artist, source: "youtube", videoId });
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (!r.ok) return null;
    const d = await r.json();
    if (d.synced) return { source: d.source || "YouTube Music", lrc: parseLrc(d.synced) };
    if (d.plain)
      return {
        source: d.source || "YouTube Music",
        lrc: d.plain.split("\n").map((t) => ({ time: -1, text: t })),
      };
    return null;
  };
  const tryLegato = async () => {
    const params = new URLSearchParams({ title, artist, source: "legato" });
    if (album) params.set("album", album);
    if (duration) params.set("duration", Math.round(duration));
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (!r.ok) return null;
    const d = await r.json();
    if (d.synced) return { source: "Better Lyrics Legato", lrc: parseLrc(d.synced) };
    return null;
  };
  const tryPortato = async () => {
    const params = new URLSearchParams({ title, artist, source: "portato" });
    if (album) params.set("album", album);
    if (duration) params.set("duration", Math.round(duration));
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (r.ok) {
      const d = await r.json();
      if (d?.qrc) {
        const lrc = parseQrc(d.qrc, { title, artist });
        if (lrc.length) return { source: "Better Lyrics Portato", lrc };
      }
    }
    return null;
  };
  const tryPaxNetease = async () => {
    const params = new URLSearchParams({ title, artist, source: "paxsenix-netease" });
    if (duration) params.set("duration", Math.round(duration));
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (r.ok) {
      const d = await r.json();
      if (d?.netease) {
        const lrc = parseNetease(d.netease, { title, artist });
        if (lrc.length) return { source: "NetEase (Paxsenix)", lrc };
      }
    }
    return null;
  };
  const tryMusixmatch = async () => {
    const params = new URLSearchParams({ title, artist, source: "musixmatch" });
    if (duration) params.set("duration", Math.round(duration));
    const r = await fetch(`${API}/lyrics?${params}`, opt);
    if (!r.ok) return null;
    const d = await r.json();
    if (d.richsync) {
      const lrc = parseRichSync(d.richsync);
      if (lrc.length) return { source: "Musixmatch", lrc };
    }
    if (d.synced) return { source: "Musixmatch", lrc: parseLrc(d.synced) };
    if (d.plain)
      return { source: "Musixmatch", lrc: d.plain.split("\n").map((t) => ({ time: -1, text: t })) };
    return null;
  };

  const tryFns = {
    better: tryBetter,
    binilyrics: tryBiniLyrics,
    portato: tryPortato,
    "paxsenix-netease": tryPaxNetease,
    unison: tryUnison,
    lrclib: tryLrclib,
    kugou: tryKugou,
    simp: trySimp,
    youtube: tryYoutube,
    legato: tryLegato,
    musixmatch: tryMusixmatch,
  };
  const enabledProviders = providers.filter((p) => p.enabled && tryFns[p.id]);

  const settled = new Map();
  // Better Lyrics falls back by actual synchronization fidelity, not response time.
  // Keep the configured provider order as the deterministic tie-break within a tier.
  const orderedResults = () =>
    enabledProviders
      .map((provider, priority) => ({ result: settled.get(provider.id), priority }))
      .filter(({ result }) => result?.lrc)
      .sort(
        (left, right) =>
          lyricsSyncQuality(right.result.providerId, right.result.lrc) -
            lyricsSyncQuality(left.result.providerId, left.result.lrc) ||
          left.priority - right.priority
      )
      .map(({ result }) => result);

  await Promise.all(
    enabledProviders.map((provider) =>
      tryFns[provider.id]()
        .catch(() => null)
        .then((result) => {
          settled.set(provider.id, result ? { ...result, providerId: provider.id } : null);
          if (!onUpdate) return;
          try {
            const results = orderedResults();
            onUpdate({
              best: results[0] || null,
              results,
              failedIds: enabledProviders
                .filter((item) => settled.get(item.id) === null)
                .map((item) => item.id),
              pending: enabledProviders
                .filter((item) => !settled.has(item.id))
                .map((item) => item.id),
            });
          } catch {
            // A view callback must never break the provider fetch.
          }
        })
    )
  );

  const allResults = orderedResults();
  const failedIds = enabledProviders
    .filter((provider) => !settled.get(provider.id))
    .map((provider) => provider.id);
  const bestResult = allResults[0] || null;

  return bestResult ? { ...bestResult, failedIds, allResults } : { failedIds, allResults };
}

// The frontend signs each request with the stored identity (WebCrypto) and posts the
// signed envelope to the backend, which forwards it to Unison.

export { fetchLyrics };
