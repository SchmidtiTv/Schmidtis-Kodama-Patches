export const EQUALIZER_STORAGE_KEY = "kodama-equalizer";
export const DEFAULT_EQUALIZER_CONFIG = {
  enabled: false,
  preampDb: 0,
  gainsDb: Array(10).fill(0),
  presetId: "default",
  custom: [],
};
const clampGain = (value) =>
  Number.isFinite(Number(value)) ? Math.max(-12, Math.min(12, Number(value))) : 0;

export function normalizeEqualizerPreset(value) {
  const gains = Array.isArray(value?.gainsDb)
    ? value.gainsDb
    : Array.isArray(value?.gains)
      ? value.gains
      : [];
  return {
    id: typeof value?.id === "string" ? value.id.slice(0, 120) : "",
    name: typeof value?.name === "string" ? value.name.slice(0, 80) : "Preset",
    preampDb: clampGain(value?.preampDb ?? value?.preamp),
    gainsDb: Array.from({ length: 10 }, (_, index) => clampGain(gains[index])),
  };
}

export function loadEqualizerState() {
  try {
    const raw = JSON.parse(localStorage.getItem(EQUALIZER_STORAGE_KEY));
    if (!raw || typeof raw !== "object") return { ...DEFAULT_EQUALIZER_CONFIG };
    const curve = normalizeEqualizerPreset(raw);
    return {
      enabled: raw.enabled === true,
      preampDb: curve.preampDb,
      gainsDb: curve.gainsDb,
      presetId: typeof raw.presetId === "string" ? raw.presetId : "default",
      custom: Array.isArray(raw.custom)
        ? raw.custom
            .filter((preset) => typeof preset?.id === "string")
            .map(normalizeEqualizerPreset)
        : [],
    };
  } catch {
    return { ...DEFAULT_EQUALIZER_CONFIG };
  }
}

export function saveEqualizerState(state) {
  try {
    localStorage.setItem(EQUALIZER_STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}
