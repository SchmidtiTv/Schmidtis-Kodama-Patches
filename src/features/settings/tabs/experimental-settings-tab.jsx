import { Button, ToggleButton, ToggleButtonGroupRoot } from "@heroui/react";
import {
  ArrowsLeftRight,
  ClapperboardPlay,
  Columns,
  Gamepad,
  MiniPlayerEnter,
  Sliders,
} from "@/shared/icons/icons.jsx";
import { SettingRow, SettingsSectionDesc, Toggle } from "@/shared/ui/settings-controls.jsx";
import { openMiniPlayer } from "@/features/player/miniplayer/bridge.js";
export function ExperimentalSettingsTab({
  onToggleVideoSync,
  onToggleRtlLayout,
  rtlLayout,
  onVideoLyricsStyleChange,
  onVideoSyncQualityChange,
  t,
  videoLyricsStyle,
  videoSyncEnabled,
  videoSyncQuality,
}) {
  return (
    <div className="flex flex-col gap-4">
      <SettingsSectionDesc
        style={{
          marginTop: 0,
        }}
      >
        {t("experimentalDesc")}
      </SettingsSectionDesc>
      <SettingRow
        label={t("bigPictureMode")}
        description={t("bigPictureModeDesc")}
        icon={<Gamepad />}
      >
        <Button
          variant="secondary"
          size="sm"
          onPress={() => window.dispatchEvent(new Event("kodama-open-bigpicture"))}
        >
          {t("bigPictureLaunch")}
        </Button>
      </SettingRow>
      <SettingRow
        label={t("miniPlayerTooltip")}
        description={t("miniPlayerOpenMain")}
        icon={<MiniPlayerEnter />}
      >
        <Button variant="secondary" size="sm" onPress={() => openMiniPlayer().catch(() => {})}>
          {t("miniPlayerTooltip")}
        </Button>
      </SettingRow>
      <SettingRow
        label={t("rtlLayout")}
        description={t("rtlLayoutDesc")}
        icon={<ArrowsLeftRight />}
      >
        <Toggle value={rtlLayout} onChange={onToggleRtlLayout} />
      </SettingRow>
      <SettingRow
        label={t("videoSyncMode")}
        description={t("videoSyncModeDesc")}
        icon={<ClapperboardPlay />}
      >
        <Toggle value={videoSyncEnabled} onChange={onToggleVideoSync} />
      </SettingRow>
      {videoSyncEnabled && (
        <SettingRow
          label={t("videoSyncQuality")}
          description={t("videoSyncQualityDesc")}
          icon={<Sliders />}
        >
          <ToggleButtonGroupRoot
            selectionMode="single"
            selectedKeys={[videoSyncQuality]}
            onSelectionChange={(keys) => {
              const value = [...keys][0];
              if (value) onVideoSyncQualityChange?.(value);
            }}
            size="sm"
          >
            <ToggleButton id="480">480p</ToggleButton>
            <ToggleButton id="720">720p</ToggleButton>
            <ToggleButton id="1080">1080p</ToggleButton>
            <ToggleButton id="auto">{t("videoSyncQualityAuto")}</ToggleButton>
          </ToggleButtonGroupRoot>
        </SettingRow>
      )}
      {videoSyncEnabled && (
        <SettingRow
          label={t("videoLyricsStyle")}
          description={t("videoLyricsStyleDesc")}
          icon={<Columns />}
        >
          <ToggleButtonGroupRoot
            selectionMode="single"
            selectedKeys={[videoLyricsStyle]}
            onSelectionChange={(keys) => {
              const value = [...keys][0];
              if (value) onVideoLyricsStyleChange?.(value);
            }}
            size="sm"
          >
            <ToggleButton id="split">{t("videoLyricsStyleSplit")}</ToggleButton>
            <ToggleButton id="captions">{t("videoLyricsStyleCaptions")}</ToggleButton>
          </ToggleButtonGroupRoot>
        </SettingRow>
      )}
    </div>
  );
}
