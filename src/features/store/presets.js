import { VIZ_DEFAULTS, cleanVisualizerConfig } from "../visualizer/index.js";
import {
  loadEqualizerState,
  normalizeEqualizerPreset,
  saveEqualizerState,
} from "../player/equalizer.js";
import { announceStoreChange } from "./events.js";

export const PRESET_KINDS = ["visualizer", "equalizer"];
export const VISUALIZER_PRESETS_KEY = "kodama-visualizer-presets";
export const VIZ_CONFIG_KEY = "kiyoshi-visualizer-config";
export function parseStoreId(value) {
  const match = /^store:([\w-]{1,64})(?:@([0-9A-Za-z.-]{1,40}))?$/.exec(String(value || ""));
  return match ? { id: match[1], version: match[2] || null } : null;
}
export function readVisualizerPresets() {
  try {
    const value = JSON.parse(localStorage.getItem(VISUALIZER_PRESETS_KEY) || "[]");
    return Array.isArray(value)
      ? value
          .filter(
            (preset) =>
              typeof preset?.id === "string" && preset?.config && typeof preset.config === "object"
          )
          .map((preset) => ({ ...preset, config: cleanVisualizerConfig(preset.config) }))
      : [];
  } catch {
    return [];
  }
}
export function writeVisualizerPresets(list) {
  try {
    localStorage.setItem(VISUALIZER_PRESETS_KEY, JSON.stringify(list));
    return true;
  } catch {
    return false;
  }
}
export function installedPresets(kind) {
  const list =
    kind === "visualizer"
      ? readVisualizerPresets()
      : kind === "equalizer"
        ? loadEqualizerState().custom
        : [];
  return list.map((preset) => parseStoreId(preset.id)).filter(Boolean);
}
export function installPreset(kind, entry) {
  if (
    !PRESET_KINDS.includes(kind) ||
    !/^[\w-]{1,64}$/.test(entry?.id || "") ||
    !entry.config ||
    typeof entry.config !== "object"
  )
    return false;
  const version =
    typeof entry.version === "string" && /^[0-9A-Za-z.-]{1,40}$/.test(entry.version)
      ? entry.version
      : "1.0.0";
  const id = `store:${entry.id}@${version}`;
  const name = typeof entry.title === "string" ? entry.title.slice(0, 80) : entry.id;
  const keep = (preset) => parseStoreId(preset.id)?.id !== entry.id;
  if (kind === "visualizer") {
    const config = cleanVisualizerConfig(entry.config);
    if (!Object.keys(config).length) return false;
    return writeVisualizerPresets([
      { id, name, config, savedAt: new Date().toISOString() },
      ...readVisualizerPresets().filter(keep),
    ]);
  }
  const state = loadEqualizerState();
  const preset = normalizeEqualizerPreset({ ...entry.config, id, name });
  const active = parseStoreId(state.presetId)?.id === entry.id;
  return saveEqualizerState({
    ...state,
    ...(active ? { presetId: id, preampDb: preset.preampDb, gainsDb: preset.gainsDb } : {}),
    custom: [...state.custom.filter(keep), preset],
  });
}
export function uninstallPreset(kind, id) {
  if (!PRESET_KINDS.includes(kind)) return false;
  const keep = (preset) => parseStoreId(preset.id)?.id !== id;
  if (kind === "visualizer") {
    const list = readVisualizerPresets();
    if (!writeVisualizerPresets(list.filter(keep))) return false;
    try {
      const active = {
        ...VIZ_DEFAULTS,
        ...JSON.parse(localStorage.getItem(VIZ_CONFIG_KEY) || "{}"),
      };
      const wasActive = list
        .filter((preset) => !keep(preset))
        .some((preset) =>
          Object.keys(VIZ_DEFAULTS).every(
            (key) => active[key] === { ...VIZ_DEFAULTS, ...preset.config }[key]
          )
        );
      if (wasActive) localStorage.setItem(VIZ_CONFIG_KEY, JSON.stringify(VIZ_DEFAULTS));
    } catch {
      /* There may be no active visualizer configuration yet. */
    }
    return true;
  }
  const state = loadEqualizerState();
  const active = parseStoreId(state.presetId)?.id === id;
  return saveEqualizerState({
    ...state,
    ...(active ? { presetId: "default", preampDb: 0, gainsDb: Array(10).fill(0) } : {}),
    custom: state.custom.filter(keep),
  });
}
export async function installPresetEverywhere(kind, entry) {
  const installed = installPreset(kind, entry);
  if (installed) await announceStoreChange(kind);
  return installed;
}
export async function uninstallPresetEverywhere(kind, id) {
  const removed = uninstallPreset(kind, id);
  if (removed) await announceStoreChange(kind);
  return removed;
}
