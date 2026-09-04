import { Button } from "@heroui/react";
import { EqualizerSettings } from "@/features/player/equalizer-settings.jsx";
import { EyeSlash, PlayCircle, Sliders, Trash, WaveformLines } from "@/shared/icons/icons.jsx";
import {
  SettingRow,
  SettingsSectionLabel,
  Slider,
  Toggle,
} from "@/shared/ui/settings-controls.jsx";

function isActiveCrossfadeOverride(key, videoIds) {
  return [...videoIds].some((fromVideoId) => {
    const prefix = `${fromVideoId}__`;
    return key.startsWith(prefix) && videoIds.has(key.slice(prefix.length));
  });
}

export function PlaybackSettingsTab({
  anonStats,
  autoplay,
  crossfade,
  crossfadeOverrides,
  crossfadeQueue,
  crossfadeDisabled,
  hideExplicit,
  onAnonStatsChange,
  onAutoplayChange,
  onCrossfadeChange,
  onHideExplicitChange,
  onPlaybackProgressiveChange,
  mixTransitionsEnabled,
  onMixTransitionsEnabledChange,
  mixTempoLockEnabled,
  onMixTempoLockEnabledChange,
  onRemoveCrossfadeOverride,
  onTrackNumbersChange,
  playbackProgressive,
  showTrackNumbers,
  t,
}) {
  const queueVideoIds = new Set((crossfadeQueue || []).map((track) => track?.videoId));
  const activeCrossfadeOverrides = Object.entries(crossfadeOverrides).filter(([key]) =>
    isActiveCrossfadeOverride(key, queueVideoIds)
  );

  return (
    <>
      <SettingsSectionLabel>{t("general")}</SettingsSectionLabel>
      <SettingRow label={t("autoplay")} description={t("autoplayDesc")} icon={<PlayCircle />}>
        <Toggle value={autoplay} onChange={onAutoplayChange} />
      </SettingRow>
      <SettingRow
        label={t("progressivePlayback") || "Progressives Laden"}
        description={
          t("progressivePlaybackDesc") ||
          "Schnellerer Start: streamt den Song statt ihn erst komplett herunterzuladen. Aus = klassisch (lädt vollständig, stabiler auf schwachen Geräten)."
        }
        icon={<WaveformLines />}
      >
        <Toggle value={playbackProgressive} onChange={onPlaybackProgressiveChange} />
      </SettingRow>
      <SettingsSectionLabel>{t("mixPlaybackTitle")}</SettingsSectionLabel>
      <EqualizerSettings t={t} />
      <SettingRow
        label={t("mixPlayback")}
        description={t("mixPlaybackDesc")}
        icon={<WaveformLines />}
      >
        <Toggle value={mixTransitionsEnabled} onChange={onMixTransitionsEnabledChange} />
      </SettingRow>
      <SettingRow
        label={t("mixTempoLock")}
        description={t("mixTempoLockDesc")}
        icon={<Sliders />}
      >
        <Toggle value={mixTempoLockEnabled} onChange={onMixTempoLockEnabledChange} />
      </SettingRow>
      <div className="text-t11 text-muted px-1 mb-2 leading-snug">{t("mixFallbackDesc")}</div>
      <SettingRow
        label={
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {t("crossfade")}
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
        }
        description={`${t("crossfadeDesc")}: ${crossfade}s${
          crossfadeDisabled ? ` · ${t("crossfadeUnavailableInVideo")}` : ""
        }`}
        icon={<Sliders />}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <Slider
            min={0}
            max={12}
            step={1}
            value={crossfade}
            onChange={onCrossfadeChange}
            width={120}
          />
          <span
            style={{
              fontSize: "var(--t12)",
              color: "var(--text-secondary)",
              width: 28,
            }}
          >
            {crossfade}s
          </span>
        </div>
      </SettingRow>
      <div
        style={{
          fontSize: "var(--t11)",
          color: "var(--text-muted)",
          margin: "-2px 0 6px",
          paddingLeft: 2,
        }}
      >
        {t("customCrossfadesDesc")}
      </div>
      {activeCrossfadeOverrides.length > 0 && (
        <div
          style={{
            margin: "2px 0 6px",
            padding: "10px 12px",
            background: "var(--fill-subtle)",
            borderRadius: "var(--r-xl)",
          }}
        >
          <div
            style={{
              fontSize: "var(--t11)",
              color: "var(--text-muted)",
              marginBottom: 8,
            }}
          >
            {t("customCrossfadesTitle")}
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            {activeCrossfadeOverrides.map(([key, ov]) => (
              <div
                key={key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: "var(--t12)",
                    color: "var(--text-primary)",
                  }}
                >
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {ov.fromTitle || key.split("__")[0]}
                  </span>
                  <span
                    style={{
                      color: "var(--accent)",
                      fontWeight: 700,
                    }}
                  >
                    →
                  </span>
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {ov.toTitle || key.split("__")[1]}
                  </span>
                </span>
                <span
                  style={{
                    fontSize: "var(--t11)",
                    fontWeight: 700,
                    color: "var(--accent)",
                    width: 30,
                    textAlign: "right",
                  }}
                >
                  {ov.secs}s
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  isIconOnly
                  className="h-7 min-w-7 text-muted hover:text-[var(--status-danger)]!"
                  onPress={() => onRemoveCrossfadeOverride?.(key)}
                >
                  <Trash size={13} />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
      <SettingRow label={t("hideExplicit")} description={t("hideExplicitDesc")} icon={<EyeSlash />}>
        <Toggle value={hideExplicit} onChange={onHideExplicitChange} />
      </SettingRow>
      <SettingRow
        label={t("trackNumbers")}
        description={t("trackNumbersDesc")}
        icon={
          <i
            className="fa-solid fa-list-ol"
            style={{
              fontSize: 15,
            }}
            aria-hidden="true"
          />
        }
      >
        <Toggle value={showTrackNumbers} onChange={onTrackNumbersChange} />
      </SettingRow>
      <SettingRow
        label={t("anonStats")}
        description={t("anonStatsDesc")}
        icon={
          <i
            className="fa-solid fa-chart-simple"
            style={{
              fontSize: 15,
            }}
            aria-hidden="true"
          />
        }
      >
        <Toggle value={anonStats} onChange={onAnonStatsChange} />
      </SettingRow>
    </>
  );
}
