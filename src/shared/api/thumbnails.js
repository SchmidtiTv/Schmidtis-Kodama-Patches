import { API } from "./client.js";

// Proxy YouTube thumbnails through the local server to avoid CORS issues.
export const thumb = (url) => (url ? `${API}/imgproxy?url=${encodeURIComponent(url)}` : "");

// Upgrade a Google usercontent thumbnail (YT Music art) to a larger square by rewriting its size
// suffix (=w120-…, =s226-…), or appending one if absent. The default thumb() keeps the small
// _pick_thumb size app-wide; use this where the cover is shown large (e.g. Big Picture).
export function hiResThumb(url, size = 512) {
  if (!url) return url;
  if (url.includes("googleusercontent.com") || url.includes("ggpht.com")) {
    if (/=[ws]\d+/.test(url)) return url.replace(/=[ws]\d+[^/]*$/, `=w${size}-h${size}-l90-rj`);
    return url + `=w${size}-h${size}-l90-rj`;
  }
  // i.ytimg.com serves fixed variants instead of an arbitrary size, and used to fall through
  // here untouched — a 48px row cell then decoded whatever the backend picked, which is
  // anything from 226px upwards. Snap to the smallest variant that still covers the request.
  if (url.includes("i.ytimg.com")) {
    const variant = size <= 120 ? "default" : size <= 320 ? "mqdefault" : size <= 480 ? "hqdefault" : "maxresdefault";
    return url.replace(/\/(maxres|sd|hq|mq)?default\.jpg/, `/${variant}.jpg`);
  }
  return url;
}

export const thumbHi = (url, size) => thumb(hiResThumb(url, size));
