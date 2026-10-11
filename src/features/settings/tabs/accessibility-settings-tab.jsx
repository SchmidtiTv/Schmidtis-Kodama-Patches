import { CardRoot, ToggleButton, ToggleButtonGroupRoot, cn } from "@heroui/react";
import { Check, CircleHalf, Sparkles, X } from "@/shared/icons/icons.jsx";
import { SettingRow, SettingsSectionLabel, Toggle } from "@/shared/ui/settings-controls.jsx";
export function AccessibilitySettingsTab({
  reduceMotionPref = "system",
  onReduceMotionChange,
  monoAudio = false,
  onToggleMonoAudio,
  accentContrast = false,
  onToggleAccentContrast,
  announceTracks = true,
  onToggleAnnounceTracks,
  ambientBackground,
  appFont,
  closeTray,
  highContrast,
  language,
  onAppFontChange,
  onCloseTrayChange,
  onToggleAmbientBackground,
  onToggleHighContrast,
  t,
}) {
  return (
    <>
      <div
        id="set-sec-acc-visual"
        data-settings-section="acc-visual"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel
          style={{
            marginTop: 4,
          }}
        >
          {t("accVisual")}
        </SettingsSectionLabel>
        <SettingRow
          label={t("highContrast")}
          description={t("highContrastDesc")}
          icon={<CircleHalf />}
        >
          <Toggle value={highContrast} onChange={onToggleHighContrast} />
        </SettingRow>
        <SettingRow
          label={t("reduceMotion")}
          description={t("reduceMotionDesc")}
          icon={<Sparkles />}
        >
          <ToggleButtonGroupRoot
            aria-label={t("reduceMotion")}
            selectionMode="single"
            disallowEmptySelection
            size="sm"
            selectedKeys={[reduceMotionPref]}
            onSelectionChange={(keys) => {
              const value = [...keys][0];
              if (value) onReduceMotionChange?.(value);
            }}
          >
            <ToggleButton id="system">{t("reduceMotionSystem")}</ToggleButton>
            <ToggleButton id="on">{t("reduceMotionOn")}</ToggleButton>
            <ToggleButton id="off">{t("reduceMotionOff")}</ToggleButton>
          </ToggleButtonGroupRoot>
        </SettingRow>
        <SettingRow
          label={t("accentContrast")}
          description={t("accentContrastDesc")}
          icon={<CircleHalf />}
        >
          <Toggle value={accentContrast} onChange={onToggleAccentContrast} />
        </SettingRow>
        <SettingRow
          label={t("ambientBackground")}
          description={t("ambientBackgroundDesc")}
          icon={<Sparkles />}
        >
          <Toggle value={ambientBackground} onChange={onToggleAmbientBackground} />
        </SettingRow>

        <SettingsSectionLabel>{t("appFont")}</SettingsSectionLabel>
        <div className="flex flex-col gap-2">
          {[
            {
              id: "default",
              label: t("appFontDefault"),
              font: "'MiSans Latin', system-ui, sans-serif",
            },
            {
              id: "dyslexic",
              label: t("appFontDyslexic"),
              font: "'OpenDyslexic', system-ui, sans-serif",
            },
          ].map((f) => (
            <CardRoot
              key={f.id}
              onClick={() => onAppFontChange(f.id)}
              role="button"
              tabIndex={0}
              aria-pressed={appFont === f.id}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onAppFontChange(f.id);
                }
              }}
              variant="secondary"
              className={cn(
                "flex flex-row items-center justify-between gap-3 px-4 py-3.5 cursor-default border-2 transition-colors",
                appFont === f.id
                  ? "border-accent bg-accent-dim"
                  : "border-transparent bg-surface-1 hover:bg-hover"
              )}
            >
              <div>
                <div
                  className="text-t13 font-semibold text-primary mb-0.5"
                  style={{
                    fontFamily: f.font,
                  }}
                >
                  {f.label}
                </div>
                <div
                  className="text-t12 text-muted"
                  style={{
                    fontFamily: f.font,
                  }}
                >
                  {language === "de"
                    ? "Franz jagt im komplett verwahrlosten Taxi quer durch Bayern"
                    : "The quick brown fox jumps over the lazy dog"}
                </div>
              </div>
              {appFont === f.id && <Check size={16} className="text-accent shrink-0 ml-3" />}
            </CardRoot>
          ))}
        </div>
      </div>

      <div
        id="set-sec-acc-behaviour"
        data-settings-section="acc-behaviour"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel
          style={{
            marginTop: 4,
          }}
        >
          {t("behaviour")}
        </SettingsSectionLabel>
        <SettingRow label={t("announceTracks")} description={t("announceTracksDesc")}>
          <Toggle value={announceTracks} onChange={onToggleAnnounceTracks} />
        </SettingRow>
        <SettingRow label={t("closeTray")} description={t("closeTrayDesc")} icon={<X />}>
          <Toggle value={closeTray} onChange={onCloseTrayChange} />
        </SettingRow>
      </div>
      <div
        id="set-sec-acc-hearing"
        data-settings-section="acc-hearing"
        style={{ scrollMarginTop: 8 }}
      >
        <SettingsSectionLabel>{t("accHearing")}</SettingsSectionLabel>
        <SettingRow label={t("monoAudio")} description={t("monoAudioDesc")}>
          <Toggle value={monoAudio} onChange={onToggleMonoAudio} />
        </SettingRow>
      </div>
    </>
  );
}
