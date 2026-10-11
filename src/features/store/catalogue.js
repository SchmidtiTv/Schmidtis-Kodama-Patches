import {
  THEME_CATALOGUE_URL,
  normalizeTheme,
  annotateThemes,
} from "../../shared/lib/theme-catalogue.js";
import {
  compareCatalogueVersions,
  supportsCatalogueEntry,
} from "../../shared/lib/catalogue-version.js";
import { installedPresets, PRESET_KINDS } from "./presets.js";

export const CATALOGUE_URL = THEME_CATALOGUE_URL;
export function normalizePresetEntry(value) {
  if (!value || typeof value !== "object" || !/^[\w-]{1,64}$/.test(value.id || "")) return null;
  if (value.schema !== undefined && value.schema !== 1) return null;
  if (!value.config || typeof value.config !== "object" || Array.isArray(value.config)) return null;
  return {
    id: value.id,
    title: typeof value.title === "string" ? value.title.slice(0, 80) : value.id,
    version: typeof value.version === "string" ? value.version.slice(0, 40) : "1.0.0",
    minVersion: typeof value.minVersion === "string" ? value.minVersion.slice(0, 40) : "",
    config: value.config,
  };
}
export async function fetchCatalogue() {
  try {
    const response = await fetch(CATALOGUE_URL, { cache: "no-cache" });
    if (!response.ok) return { ok: false };
    const data = await response.json();
    if (!data || (data.schema !== undefined && data.schema !== 1) || !Array.isArray(data.themes))
      return { ok: false };
    const catalogue = {
      ok: true,
      themes: annotateThemes(data.themes.map(normalizeTheme).filter(Boolean)),
    };
    for (const kind of PRESET_KINDS) {
      const installed = installedPresets(kind);
      catalogue[kind] = (Array.isArray(data[kind]) ? data[kind] : [])
        .map(normalizePresetEntry)
        .filter(Boolean)
        .map((entry) => {
          const local = installed.find((preset) => preset.id === entry.id);
          return {
            ...entry,
            supported: supportsCatalogueEntry(entry),
            installed: !!local,
            updatable:
              !!local?.version && compareCatalogueVersions(entry.version, local.version) > 0,
          };
        });
    }
    return catalogue;
  } catch {
    return { ok: false };
  }
}
