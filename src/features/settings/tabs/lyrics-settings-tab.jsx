import { ToggleButton, ToggleButtonGroupRoot } from "@heroui/react";
import {
  ComposerSettingsSection,
  LyricsProviderList,
  UnisonIdentitySection,
} from "../settings-support.jsx";
import { DEFAULT_LYRICS_PROVIDERS } from "@/features/lyrics";
import { Globe, Sparkles, Tag, TextSize, Translate, WaveformLines } from "@/shared/icons/icons.jsx";
import {
  SettingRow,
  SettingsSectionDesc,
  SettingsSectionLabel,
  Slider,
  Toggle,
} from "@/shared/ui/settings-controls.jsx";
export function LyricsSettingsTab({
  lyricsEngine = "braccato",
  onLyricsEngineChange,
  braccatoLetterWave = true,
  onToggleBraccatoLetterWave,
  fluidLyrics,
  lyricsFontSize,
  lyricsProviders,
  lyricsRomajiFontSize,
  lyricsTranslationFontSize,
  onLyricsFontSizeChange,
  onLyricsProvidersChange,
  onLyricsRomajiFontSizeChange,
  onLyricsTranslationFontSizeChange,
  onToggleAgentTags,
  onToggleFluidLyrics,
  onToggleRomaji,
  onToggleSyllableZoom,
  showAgentTags,
  showRomaji,
  syllableZoom,
  t,
}) {
  return (
    <>
      <div
        id="set-sec-lyrics-visual"
        data-settings-section="lyrics-visual"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel
          style={{
            marginTop: 4,
          }}
        >
          {t("lyrVisual")}
        </SettingsSectionLabel>
        <SettingRow
          label={t("fontSize")}
          description={`${t("fontSizeDesc")}: ${lyricsFontSize}px`}
          icon={<TextSize />}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Slider
              min={18}
              max={52}
              step={2}
              value={lyricsFontSize}
              onChange={onLyricsFontSizeChange}
              width={120}
            />
            <span
              style={{
                fontSize: "var(--t12)",
                color: "var(--text-secondary)",
                width: 36,
              }}
            >
              {lyricsFontSize}px
            </span>
          </div>
        </SettingRow>
        <SettingRow
          label={t("translationFontSize")}
          description={`${t("fontSizeDesc")}: ${lyricsTranslationFontSize}px`}
          icon={<Translate />}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Slider
              min={12}
              max={40}
              step={2}
              value={lyricsTranslationFontSize}
              onChange={onLyricsTranslationFontSizeChange}
              width={120}
            />
            <span
              style={{
                fontSize: "var(--t12)",
                color: "var(--text-secondary)",
                width: 36,
              }}
            >
              {lyricsTranslationFontSize}px
            </span>
          </div>
        </SettingRow>
        <SettingRow
          label={t("romajiFontSize")}
          description={`${t("fontSizeDesc")}: ${lyricsRomajiFontSize}px`}
          icon={<TextSize />}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Slider
              min={12}
              max={40}
              step={2}
              value={lyricsRomajiFontSize}
              onChange={onLyricsRomajiFontSizeChange}
              width={120}
            />
            <span
              style={{
                fontSize: "var(--t12)",
                color: "var(--text-secondary)",
                width: 36,
              }}
            >
              {lyricsRomajiFontSize}px
            </span>
          </div>
        </SettingRow>
        <SettingRow label={t("showRomaji")} description={t("romajiLyrics")} icon={<Globe />}>
          <Toggle value={showRomaji} onChange={onToggleRomaji} />
        </SettingRow>
        <SettingRow label={t("showAgentTags")} description={t("showAgentTagsDesc")} icon={<Tag />}>
          <Toggle value={showAgentTags} onChange={onToggleAgentTags} />
        </SettingRow>
      </div>

      <div
        id="set-sec-lyrics-effects"
        data-settings-section="lyrics-effects"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel>{t("lyrEffects")}</SettingsSectionLabel>
        <SettingRow
          label={t("lyricsEngine")}
          description={t("lyricsEngineDesc")}
          icon={<WaveformLines />}
        >
          <ToggleButtonGroupRoot
            aria-label={t("lyricsEngine")}
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[lyricsEngine]}
            size="sm"
            onSelectionChange={(keys) => {
              const value = [...keys][0];
              if (value) onLyricsEngineChange?.(value);
            }}
          >
            <ToggleButton id="braccato">{t("lyricsEngineBraccato")}</ToggleButton>
            <ToggleButton id="legacy">{t("lyricsEngineLegacy")}</ToggleButton>
          </ToggleButtonGroupRoot>
        </SettingRow>
        {lyricsEngine === "braccato" ? (
          <SettingRow
            label={t("braccatoLetterWave")}
            description={t("braccatoLetterWaveDesc")}
            icon={<Sparkles />}
          >
            <Toggle value={braccatoLetterWave} onChange={onToggleBraccatoLetterWave} />
          </SettingRow>
        ) : (
          <>
            {" "}
            <SettingRow
              label={t("syllableZoom")}
              description={t("syllableZoomDesc")}
              icon={<Sparkles />}
            >
              <Toggle value={syllableZoom} onChange={onToggleSyllableZoom} />
            </SettingRow>
            <SettingRow
              label={t("fluidLyrics")}
              description={t("fluidLyricsDesc")}
              icon={<WaveformLines />}
            >
              <Toggle value={fluidLyrics} onChange={onToggleFluidLyrics} />
            </SettingRow>
          </>
        )}
      </div>

      <div
        id="set-sec-lyrics-providers"
        data-settings-section="lyrics-providers"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel>{t("lyricsProviders")}</SettingsSectionLabel>
        <SettingsSectionDesc>{t("lyricsProvidersDesc")}</SettingsSectionDesc>
        <LyricsProviderList
          providers={lyricsProviders || DEFAULT_LYRICS_PROVIDERS}
          onChange={onLyricsProvidersChange}
        />
      </div>

      <div
        id="set-sec-lyrics-unison"
        data-settings-section="lyrics-unison"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <UnisonIdentitySection />
      </div>

      <div
        id="set-sec-lyrics-composer"
        data-settings-section="lyrics-composer"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <ComposerSettingsSection />
      </div>
    </>
  );
}
