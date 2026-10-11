import {
  BUILTIN_THEMES,
  readInstalledThemes,
  sanitizeTokens,
  writeInstalledThemes,
} from "./themes.js";
import { compareCatalogueVersions, supportsCatalogueEntry } from "./catalogue-version.js";

export const THEME_CATALOGUE_URL =
  "https://raw.githubusercontent.com/KiyoshiTheDevil/kodama-store/main/index.json";

export function normalizeTheme(value) {
  if (!value || typeof value !== "object" || !/^[\w-]{1,64}$/.test(value.id || "")) return null;
  if (value.schema !== undefined && (!Number.isInteger(value.schema) || value.schema !== 1))
    return null;
  const tokens = sanitizeTokens(value.tokens);
  if (!Object.keys(tokens).length) return null;
  return {
    id: value.id,
    title: typeof value.title === "string" ? value.title.slice(0, 40) : value.id,
    description: typeof value.description === "string" ? value.description.slice(0, 300) : "",
    version: typeof value.version === "string" ? value.version.slice(0, 24) : "1.0.0",
    minVersion: typeof value.minVersion === "string" ? value.minVersion.slice(0, 40) : "",
    mode: value.mode === "light" ? "light" : "dark",
    tokens,
  };
}

export function annotateThemes(themes) {
  const installed = new Map(readInstalledThemes().map((theme) => [theme.id, theme]));
  return themes.map((theme) => {
    const local = installed.get(theme.id);
    return {
      ...theme,
      builtin: BUILTIN_THEMES.some((builtin) => builtin.id === theme.id),
      installed: !!local,
      installedVersion: local?.version,
      updatable: !!local && compareCatalogueVersions(theme.version, local.version) > 0,
      supported: supportsCatalogueEntry(theme),
    };
  });
}

export async function fetchThemeCatalogue() {
  try {
    const response = await fetch(THEME_CATALOGUE_URL, { cache: "no-cache" });
    const data = await response.json();
    if (
      !response.ok ||
      (data.schema !== undefined && data.schema !== 1) ||
      !Array.isArray(data?.themes)
    )
      return [];
    return annotateThemes(data.themes.map(normalizeTheme).filter(Boolean));
  } catch {
    return [];
  }
}

export function installTheme(theme) {
  const safe = normalizeTheme(theme);
  if (
    !safe ||
    !supportsCatalogueEntry(safe) ||
    BUILTIN_THEMES.some((builtin) => builtin.id === safe.id)
  )
    return false;
  const next = readInstalledThemes().filter((installed) => installed.id !== safe.id);
  next.push({
    id: safe.id,
    label: safe.title,
    mode: safe.mode,
    version: safe.version,
    tokens: safe.tokens,
  });
  return writeInstalledThemes(next);
}

export function uninstallTheme(id) {
  if (BUILTIN_THEMES.some((builtin) => builtin.id === id)) return false;
  return writeInstalledThemes(readInstalledThemes().filter((theme) => theme.id !== id));
}
