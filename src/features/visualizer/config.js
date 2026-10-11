import { VIZ_DEFAULTS } from "./defaults.js";
const enums = {
  shape: ["frame", "ring", "linear"],
  linearPos: ["bottom", "center"],
  render: ["bars", "curve"],
  barCap: ["round", "square"],
  color: ["accent", "cover", "custom"],
  coverShape: ["rounded", "circle"],
};
const ranges = {
  barCount: [8, 160],
  barLength: [8, 260],
  barThickness: [1, 16],
  gap: [0, 80],
  responsiveness: [0, 1],
  floor: [0, 0.9],
  ceiling: [0.1, 1],
  tilt: [0, 1],
  smoothBands: [0, 1],
  coverPulseStrength: [0, 1],
};
export function cleanVisualizerConfig(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out = {};
  for (const [key, fallback] of Object.entries(VIZ_DEFAULTS)) {
    const item = value[key];
    if (enums[key]) {
      if (enums[key].includes(item)) out[key] = item;
    } else if (ranges[key]) {
      if (typeof item === "number" && Number.isFinite(item)) {
        const [min, max] = ranges[key];
        out[key] = Math.max(min, Math.min(max, item));
        if (key === "barCount") out[key] = Math.round(out[key]);
      }
    } else if (typeof fallback === "boolean") {
      if (typeof item === "boolean") out[key] = item;
    } else if (
      (key === "customColor" || key === "gradColor") &&
      typeof item === "string" &&
      /^#(?:[\da-f]{3}|[\da-f]{6})$/i.test(item)
    )
      out[key] = item;
  }
  if (out.floor !== undefined && out.ceiling !== undefined && out.floor >= out.ceiling) {
    out.floor = 0;
    out.ceiling = 1;
  }
  return out;
}
