import { useEffect, useState } from "react";

import { native } from "@/shared/api/tauri.js";
import { Sliders } from "@/shared/icons/icons.jsx";
import { SettingRow, Slider, Toggle } from "@/shared/ui/settings-controls.jsx";

const STORAGE_KEY = "kodama-equalizer";
const FREQUENCIES = ["32", "64", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"];
const DEFAULT_CONFIG = { enabled: false, preampDb: 0, gainsDb: Array(10).fill(0) };

function loadConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (Array.isArray(saved?.gainsDb) && saved.gainsDb.length === 10) {
      return { ...DEFAULT_CONFIG, ...saved, gainsDb: saved.gainsDb.map((gain) => Number(gain) || 0) };
    }
  } catch {
    // The native equalizer safely starts flat when an older preference is invalid.
  }
  return DEFAULT_CONFIG;
}

export function EqualizerSettings({ t }) {
  const [config, setConfig] = useState(loadConfig);

  useEffect(() => {
    native.setAudioEqualizer(config.enabled, config.preampDb, config.gainsDb).catch(() => {});
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  }, [config]);

  const updateGain = (index, gain) => {
    setConfig((current) => ({
      ...current,
      gainsDb: current.gainsDb.map((value, currentIndex) => currentIndex === index ? gain : value),
    }));
  };

  return (
    <>
      <SettingRow label={t("equalizer") || "Equalizer"} description={t("equalizerDesc") || "Ten-band playback EQ"} icon={<Sliders />}>
        <Toggle value={config.enabled} onChange={(enabled) => setConfig((current) => ({ ...current, enabled }))} />
      </SettingRow>
      {config.enabled && (
        <div className="px-3 py-3 mb-2 rounded-[var(--r-lg)] bg-[var(--fill-subtle)]">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-t11 text-muted w-12">Preamp</span>
            <Slider min={-12} max={12} step={0.5} value={config.preampDb} onChange={(preampDb) => setConfig((current) => ({ ...current, preampDb }))} width={180} />
            <span className="text-t11 text-primary tabular-nums">{config.preampDb.toFixed(1)} dB</span>
          </div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-2">
            {FREQUENCIES.map((frequency, index) => (
              <label key={frequency} className="flex items-center gap-2 text-t11 text-muted">
                <span className="w-7">{frequency}</span>
                <Slider min={-12} max={12} step={0.5} value={config.gainsDb[index]} onChange={(gain) => updateGain(index, gain)} width={110} />
                <span className="w-10 text-right tabular-nums">{config.gainsDb[index].toFixed(1)}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
