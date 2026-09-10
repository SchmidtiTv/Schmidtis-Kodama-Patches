import { BUILTIN_THEMES, readInstalledThemes, sanitizeTokens, writeInstalledThemes } from "./themes.js";

export const THEME_CATALOGUE_URL = "https://raw.githubusercontent.com/KiyoshiTheDevil/kodama-store/main/index.json";

function normalizeTheme(value) {
  if (!value || typeof value !== "object" || !/^[\w-]{1,64}$/.test(value.id || "")) return null;
  const tokens = sanitizeTokens(value.tokens);
  if (!Object.keys(tokens).length) return null;
  return {
    id: value.id,
    title: typeof value.title === "string" ? value.title.slice(0, 40) : value.id,
    description: typeof value.description === "string" ? value.description.slice(0, 300) : "",
    version: typeof value.version === "string" ? value.version.slice(0, 24) : "1.0.0",
    mode: value.mode === "light" ? "light" : "dark",
    tokens,
  };
}

export async function fetchThemeCatalogue() {
  try {
    const response = await fetch(THEME_CATALOGUE_URL, { cache: "no-cache" });
    const data = await response.json();
    if (!response.ok || !Array.isArray(data?.themes)) return [];
    const installed = new Map(readInstalledThemes().map((theme) => [theme.id, theme]));
    return data.themes.map(normalizeTheme).filter(Boolean).map((theme) => ({
      ...theme,
      builtin: BUILTIN_THEMES.some((builtin) => builtin.id === theme.id),
      installed: installed.has(theme.id),
    }));
  } catch {
    return [];
  }
}

export function installTheme(theme) {
  const safe = normalizeTheme(theme);
  if (!safe) return false;
  const next = readInstalledThemes().filter((installed) => installed.id !== safe.id);
  next.push({ id: safe.id, label: safe.title, mode: safe.mode, version: safe.version, tokens: safe.tokens });
  return writeInstalledThemes(next);
}
