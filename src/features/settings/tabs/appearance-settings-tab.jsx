import {
  APP_ICON_GROUPS,
  FONT_LABELS,
  FONT_STEPS,
  ZOOM_LABELS,
  ZOOM_STEPS,
} from "../settings-constants.js";
import { AccentColorPicker } from "../settings-integration-controls.jsx";
import { Button, CardRoot, cn } from "@heroui/react";
import {
  Check,
  MagnifyingGlass,
  PaintBrushBroad,
  Sparkles,
  TextSize,
} from "@/shared/icons/icons.jsx";
import { PlayerBarCustomizer } from "../player-bar-customizer.jsx";
import {
  SettingRow,
  SettingsSectionLabel,
  Slider,
  Toggle,
} from "@/shared/ui/settings-controls.jsx";
export function AppearanceSettingsTab({
  accent,
  accentDynamic,
  accentLight,
  accentSat,
  anim,
  animations,
  appFontScale,
  appIcon,
  appIconCustomizationAvailable,
  onAccentChange,
  onAccentDynamicChange,
  onAccentLightChange,
  onAccentSatChange,
  onAnimationsChange,
  onAppIconChange,
  onFontScaleChange,
  onPlayerBarControlToggle,
  onThemeChange,
  onUiZoomChange,
  playerBarControls,
  t,
  theme,
  uiZoom,
  vizPreviewTrack,
}) {
  return (
    <>
      <div
        id="set-sec-ap-theme"
        data-settings-section="ap-theme"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel>{t("theme")}</SettingsSectionLabel>
        <div
          style={{
            display: "flex",
            gap: 12,
            marginBottom: 8,
          }}
        >
          {[
            {
              id: "dark",
              label: t("themeDark"),
              bg: "#0d0d0d",
              surface: "#141414",
              elevated: "#1c1c1c",
              text: "#f0f0f0",
            },
            {
              id: "oled",
              label: t("themeOled"),
              bg: "#000000",
              surface: "#080808",
              elevated: "#0f0f0f",
              text: "#ffffff",
            },
            {
              id: "light",
              label: t("themeLight"),
              bg: "#f0f0f0",
              surface: "#ffffff",
              elevated: "#e4e4e4",
              text: "#111111",
            },
          ].map((th) => (
            <CardRoot
              key={th.id}
              data-testid={`theme-${th.id}`}
              onClick={() => onThemeChange(th.id)}
              variant="transparent"
              className={cn(
                "relative flex-1 p-0 gap-0 rounded-[10px] overflow-hidden cursor-default border-2",
                anim && "transition-transform",
                theme === th.id
                  ? "border-accent shadow-[0_0_0_2px_var(--accent)]"
                  : "border-border",
                theme === th.id && anim && "scale-[1.02]",
                anim && "hover:scale-[1.03]"
              )}
            >
              {theme === th.id && (
                <div className="absolute top-1.5 right-1.5 z-10 w-5 h-5 rounded-full bg-accent flex items-center justify-center shadow-md">
                  <Check size={12} weight="bold" className="text-white" />
                </div>
              )}
              {/* Mini preview */}
              <div
                style={{
                  background: th.bg,
                  padding: 10,
                  height: 80,
                }}
              >
                <div
                  style={{
                    background: th.surface,
                    borderRadius: "var(--r-md)",
                    padding: "6px 8px",
                    marginBottom: 5,
                  }}
                >
                  <div
                    style={{
                      width: "60%",
                      height: 5,
                      borderRadius: 3,
                      background: accent,
                      marginBottom: 4,
                    }}
                  />
                  <div
                    style={{
                      width: "40%",
                      height: 4,
                      borderRadius: 3,
                      background: th.text,
                      opacity: 0.3,
                    }}
                  />
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 4,
                  }}
                >
                  <div
                    style={{
                      flex: 1,
                      background: th.elevated,
                      borderRadius: "var(--r-sm)",
                      height: 24,
                    }}
                  />
                  <div
                    style={{
                      flex: 1,
                      background: th.elevated,
                      borderRadius: "var(--r-sm)",
                      height: 24,
                    }}
                  />
                </div>
              </div>
              {/* Label */}
              <div
                style={{
                  background: th.surface,
                  padding: "7px 10px",
                  fontSize: "var(--t12)",
                  fontWeight: 500,
                  color: theme === th.id ? accent : th.text,
                  textAlign: "center",
                  borderTop: `1px solid ${th.id === "light" ? "rgba(0,0,0,0.1)" : "rgba(255,255,255,0.06)"}`,
                }}
              >
                {th.label}
              </div>
            </CardRoot>
          ))}
        </div>
      </div>

      {appIconCustomizationAvailable && <div
        id="set-sec-ap-icon"
        data-settings-section="ap-icon"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {t("appIcon")}
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: "0.04em",
                background: "var(--accent)",
                color: "#fff",
                padding: "2px 5px",
                borderRadius: "var(--r-sm)",
                lineHeight: 1.4,
              }}
            >
              Beta
            </span>
          </span>
        </SettingsSectionLabel>
        <div
          style={{
            fontSize: "var(--t11)",
            color: "var(--text-muted)",
            margin: "-2px 0 10px",
            paddingLeft: 2,
          }}
        >
          {t("appIconDesc")}
        </div>
        {APP_ICON_GROUPS.map((group) => (
          <div
            key={group.id}
            style={{
              marginBottom: 12,
            }}
          >
            <div
              style={{
                fontSize: "var(--t11)",
                fontWeight: 600,
                color: "var(--text-secondary)",
                marginBottom: 7,
              }}
            >
              {t(group.labelKey)}
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(60px, 1fr))",
                gap: 10,
              }}
            >
              {group.icons.map((ic) => {
                const selected = appIcon === ic.file;
                return (
                  <button
                    key={ic.file}
                    onClick={() => onAppIconChange?.(ic.file)}
                    title={ic.label}
                    className={cn(
                      "relative p-0 rounded-[14px] overflow-hidden cursor-default border-2 aspect-square bg-transparent",
                      anim && "transition-transform hover:scale-[1.05]",
                      selected
                        ? "border-accent shadow-[0_0_0_2px_var(--accent)]"
                        : "border-transparent"
                    )}
                  >
                    <img
                      src={`/App-Icons/${encodeURIComponent(ic.file)}`}
                      alt={ic.label}
                      draggable={false}
                      className="w-full h-full object-cover block"
                    />
                    {selected && (
                      <div className="absolute top-1 right-1 w-4 h-4 rounded-full bg-accent flex items-center justify-center shadow-md">
                        <Check size={10} weight="bold" className="text-white" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>}

      <div
        id="set-sec-ap-colors"
        data-settings-section="ap-colors"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel>{t("apColors")}</SettingsSectionLabel>
        <div className="flex gap-1.5 mb-3">
          <Button
            variant={!accentDynamic ? "secondary" : "ghost"}
            size="sm"
            onPress={() => onAccentDynamicChange(false)}
          >
            {t("accentCustom") || "Custom"}
          </Button>
          <Button
            variant={accentDynamic ? "secondary" : "ghost"}
            size="sm"
            onPress={() => onAccentDynamicChange(true)}
          >
            {t("visualizerDynamic") || "Dynamic"}
          </Button>
        </div>
        {accentDynamic ? (
          <>
            <div
              className="flex items-center gap-3 mb-2 rounded-xl border border-border px-4 py-3.5"
              style={{
                background: "color-mix(in srgb, var(--accent) 8%, transparent)",
              }}
            >
              <span
                className="w-8 h-8 rounded-full shrink-0"
                style={{
                  background: "var(--accent)",
                  boxShadow: "0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent)",
                }}
              />
              <span
                style={{
                  fontSize: "var(--t13)",
                  color: "var(--text-secondary)",
                }}
              >
                {t("accentDynamicDesc") ||
                  "The accent colour is derived live from the current track's cover art."}
              </span>
            </div>
            <SettingRow label={t("accentVibrancy") || "Vibrancy"} icon={<PaintBrushBroad />}>
              <Slider
                min={0}
                max={100}
                step={5}
                value={Math.round((accentSat ?? 0.5) * 100)}
                onChange={(v) => onAccentSatChange(v / 100)}
                width={200}
              />
            </SettingRow>
            <SettingRow label={t("accentBrightness") || "Brightness"} icon={<Sparkles />}>
              <Slider
                min={30}
                max={85}
                step={5}
                value={Math.round((accentLight ?? 0.6) * 100)}
                onChange={(v) => onAccentLightChange(v / 100)}
                width={200}
              />
            </SettingRow>
          </>
        ) : (
          <AccentColorPicker value={accent} onChange={onAccentChange} />
        )}
      </div>

      <div
        id="set-sec-ap-others"
        data-settings-section="ap-others"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel>{t("apOthers")}</SettingsSectionLabel>
        <SettingRow label={t("animations")} description={t("animationsDesc")} icon={<Sparkles />}>
          <Toggle value={animations} onChange={onAnimationsChange} />
        </SettingRow>
        <SettingRow label={t("uiZoom")} description={t("uiZoomDesc")} icon={<MagnifyingGlass />}>
          <div
            style={{
              width: 360,
            }}
          >
            <Slider
              min={0}
              max={ZOOM_STEPS.length - 1}
              step={1}
              value={Math.max(0, ZOOM_STEPS.indexOf(uiZoom))}
              onChange={(i) => onUiZoomChange(ZOOM_STEPS[i])}
              width={360}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: 6,
              }}
            >
              {ZOOM_LABELS.map((label, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: "var(--t10)",
                    fontWeight: uiZoom === ZOOM_STEPS[i] ? 700 : 400,
                    color: uiZoom === ZOOM_STEPS[i] ? "var(--accent)" : "var(--text-muted)",
                  }}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        </SettingRow>
        <SettingRow label={t("fontSize")} description={t("fontSizeDesc")} icon={<TextSize />}>
          <div
            style={{
              width: 360,
            }}
          >
            <Slider
              min={0}
              max={FONT_STEPS.length - 1}
              step={1}
              value={Math.max(0, FONT_STEPS.indexOf(appFontScale))}
              onChange={(i) => onFontScaleChange(FONT_STEPS[i])}
              width={360}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: 6,
              }}
            >
              {FONT_LABELS.map((label, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: "var(--t10)",
                    fontWeight: appFontScale === FONT_STEPS[i] ? 700 : 400,
                    color: appFontScale === FONT_STEPS[i] ? "var(--accent)" : "var(--text-muted)",
                  }}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        </SettingRow>
      </div>
      <div
        id="set-sec-ap-player"
        data-settings-section="ap-player"
        style={{
          scrollMarginTop: 8,
        }}
      >
        <SettingsSectionLabel>{t("playerBar")}</SettingsSectionLabel>
        <PlayerBarCustomizer
          controls={playerBarControls}
          onToggleControl={onPlayerBarControlToggle}
          t={t}
          track={vizPreviewTrack}
        />
      </div>
    </>
  );
}
