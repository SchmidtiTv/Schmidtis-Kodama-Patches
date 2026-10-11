export const STORE_WEB_URL = "https://kodama.kiyoshi.dev/store/";
export const STORE_LINK_KINDS = ["themes", "visualizer", "equalizer", "widgets", "extensions"];

export async function openStoreWeb(kind) {
  if (kind && !STORE_LINK_KINDS.includes(kind)) throw new Error("Unknown store category");
  const url = kind ? `${STORE_WEB_URL}?c=${encodeURIComponent(kind)}` : STORE_WEB_URL;
  const { openUrl } = await import("@tauri-apps/plugin-opener");
  return openUrl(url);
}

export function parseStoreLink(value) {
  const match = /^kodama:\/\/store\/([a-z]+)\/([A-Za-z0-9][A-Za-z0-9._-]{0,79})\/?$/.exec(
    String(value || "").trim()
  );
  if (!match || !STORE_LINK_KINDS.includes(match[1])) return null;
  return { kind: match[1], id: match[2] };
}
