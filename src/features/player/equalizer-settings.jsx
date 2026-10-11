import { useEffect, useState } from "react";
import { Button, CardRoot } from "@heroui/react";

import { native } from "@/shared/api/tauri.js";
import { Sliders } from "@/shared/icons/icons.jsx";
import { SettingRow, Slider, Toggle } from "@/shared/ui/settings-controls.jsx";

import {
  DEFAULT_EQUALIZER_CONFIG,
  loadEqualizerState,
  saveEqualizerState,
} from "./equalizer-presets.js";
import { onStoreChanged, announceStoreChange, openStoreWeb } from "@/features/store";
const FREQUENCIES = ["32", "64", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"];
export function EqualizerSettings({ t }) {
  const [config, setConfig] = useState(loadEqualizerState);

  const [presetName, setPresetName] = useState("");
  useEffect(
    () =>
      onStoreChanged((kind) => {
        if (kind === "equalizer")
          setConfig((current) => {
            const next = loadEqualizerState();
            return JSON.stringify(next) === JSON.stringify(current) ? current : next;
          });
      }),
    []
  );
  const savePreset = () => {
    const name = presetName.trim();
    if (!name) return;
    setConfig((current) => ({
      ...current,
      custom: [
        ...current.custom,
        {
          id: crypto.randomUUID(),
          name,
          preampDb: current.preampDb,
          gainsDb: [...current.gainsDb],
        },
      ],
    }));
    setPresetName("");
  };
  const removePreset = (id) => {
    setConfig((current) => ({
      ...current,
      ...(current.presetId === id
        ? { presetId: "default", preampDb: 0, gainsDb: Array(10).fill(0) }
        : {}),
      custom: current.custom.filter((preset) => preset.id !== id),
    }));
  };

  useEffect(() => {
    native.setAudioEqualizer(config.enabled, config.preampDb, config.gainsDb).catch(() => {});
    if (saveEqualizerState(config)) announceStoreChange("equalizer");
  }, [config]);

  const updateGain = (index, gain) => {
    setConfig((current) => ({
      ...current,
      presetId: "custom",
      gainsDb: current.gainsDb.map((value, currentIndex) =>
        currentIndex === index ? gain : value
      ),
    }));
  };

  return (
    <>
      <SettingRow label={t("equalizer")} description={t("equalizerDesc")} icon={<Sliders />}>
        <Toggle
          ariaLabel={t("equalizer")}
          value={config.enabled}
          onChange={(enabled) => setConfig((current) => ({ ...current, enabled }))}
        />
      </SettingRow>
      <div className="flex items-center justify-between gap-3 my-3">
        <span className="text-t13 font-semibold">{t("eqPresets")}</span>
        <Button
          size="sm"
          variant="secondary"
          onPress={() => openStoreWeb("equalizer").catch(() => {})}
        >
          {t("eqBrowsePresets")}
        </Button>
      </div>
      <div className="flex flex-col gap-2 mb-3">
        <Button
          size="sm"
          variant="ghost"
          onPress={() =>
            setConfig((current) => ({
              ...current,
              preampDb: 0,
              gainsDb: [...DEFAULT_EQUALIZER_CONFIG.gainsDb],
              presetId: "default",
            }))
          }
        >
          {t("resetToDefault")}
        </Button>
        {config.custom.map((preset) => (
          <div key={preset.id} className="flex items-center gap-2">
            <Button
              size="sm"
              variant={config.presetId === preset.id ? "secondary" : "ghost"}
              className="flex-1 justify-start"
              onPress={() =>
                setConfig((current) => ({
                  ...current,
                  presetId: preset.id,
                  enabled: true,
                  preampDb: preset.preampDb,
                  gainsDb: [...preset.gainsDb],
                }))
              }
            >
              {preset.name}
            </Button>
            <Button size="sm" variant="ghost" onPress={() => removePreset(preset.id)}>
              {t("themeRemove")}
            </Button>
          </div>
        ))}
        <div className="flex items-center gap-2">
          <input
            value={presetName}
            onChange={(event) => setPresetName(event.target.value)}
            aria-label={t("eqPresetName")}
            placeholder={t("eqPresetName")}
            className="min-w-0 flex-1 rounded-lg bg-surface-1 px-3 py-2 text-t12"
            onKeyDown={(event) => {
              if (event.key === "Enter") savePreset();
            }}
          />
          <Button
            size="sm"
            variant="secondary"
            isDisabled={!presetName.trim()}
            onPress={savePreset}
          >
            {t("eqSave")}
          </Button>
        </div>
      </div>
      {config.enabled && (
        <CardRoot
          variant="secondary"
          className="bg-surface-1 px-[18px] py-4 mb-1.5"
          data-testid="equalizer-controls"
        >
          <div className="flex items-center gap-3 mb-3">
            <span className="text-t11 text-muted min-w-24">{t("equalizerPreamp")}</span>
            <Slider
              min={-12}
              max={12}
              step={0.5}
              value={config.preampDb}
              onChange={(preampDb) =>
                setConfig((current) => ({ ...current, preampDb, presetId: "custom" }))
              }
              width={180}
            />
            <span className="text-t11 text-primary tabular-nums">
              {config.preampDb.toFixed(1)} dB
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-2">
            {FREQUENCIES.map((frequency, index) => (
              <label key={frequency} className="flex items-center gap-2 text-t11 text-muted">
                <span className="w-7">{frequency}</span>
                <Slider
                  min={-12}
                  max={12}
                  step={0.5}
                  value={config.gainsDb[index]}
                  onChange={(gain) => updateGain(index, gain)}
                  width={110}
                />
                <span className="w-10 text-right tabular-nums">
                  {config.gainsDb[index].toFixed(1)}
                </span>
              </label>
            ))}
          </div>
        </CardRoot>
      )}
    </>
  );
}
