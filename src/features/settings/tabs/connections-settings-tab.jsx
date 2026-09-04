import {
  ClockCounterClockwise,
  DeviceMobile,
  Info,
  ShareNodes,
  WifiHigh,
} from "@/shared/icons/icons.jsx";
import { LastfmRow } from "../settings-integration-controls.jsx";
import { RemoteControlPanel } from "@/features/remote";
import { SettingRow, Toggle } from "@/shared/ui/settings-controls.jsx";
import { ToggleButton, ToggleButtonGroupRoot } from "@heroui/react";
export function ConnectionsSettingsTab({
  discordRpc,
  discordStatusDisplay,
  hideDiscordWhilePaused,
  ipv4First,
  onDiscordRpcChange,
  onDiscordStatusDisplayChange,
  onHideDiscordWhilePausedChange,
  onIpv4FirstChange,
  onPairDevice,
  onRememberDevice,
  onRemoteDevice,
  onToggleRemote,
  onYtmusicHistorySyncChange,
  remoteDevices,
  remoteEnabled,
  remoteTrustedIds,
  t,
  ytmusicHistorySync,
}) {
  return (
    <>
      <SettingRow label={t("discordRpc")} description={t("discordRpcDesc")} icon={<ShareNodes />}>
        <Toggle value={discordRpc} onChange={onDiscordRpcChange} />
      </SettingRow>
      {discordRpc && (
        <SettingRow
          label={t("discordStatusDisplay")}
          description={t("discordStatusDisplayDesc")}
          icon={<Info size={15} />}
        >
          <ToggleButtonGroupRoot
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[discordStatusDisplay]}
            onSelectionChange={(keys) => {
              const value = [...keys][0];
              if (value) onDiscordStatusDisplayChange?.(value);
            }}
            size="sm"
          >
            <ToggleButton id="song">{t("discordStatusDisplaySong")}</ToggleButton>
            <ToggleButton id="artist">{t("discordStatusDisplayArtist")}</ToggleButton>
            <ToggleButton id="app">{t("discordStatusDisplayApp")}</ToggleButton>
          </ToggleButtonGroupRoot>
        </SettingRow>
      )}
      {discordRpc && (
        <SettingRow label={t("discordHideWhilePaused")} description={t("discordHideWhilePausedDesc")} icon={<Info size={15} />}>
          <Toggle value={hideDiscordWhilePaused} onChange={onHideDiscordWhilePausedChange} />
        </SettingRow>
      )}
      <SettingRow label={t("ipv4First")} description={t("ipv4FirstDesc")} icon={<WifiHigh />}>
        <Toggle value={ipv4First} onChange={onIpv4FirstChange} />
      </SettingRow>
      <LastfmRow />
      <SettingRow
        label={t("ytmusicHistorySync")}
        description={t("ytmusicHistorySyncDesc")}
        icon={<ClockCounterClockwise />}
      >
        <Toggle value={ytmusicHistorySync} onChange={onYtmusicHistorySyncChange} />
      </SettingRow>
      <SettingRow
        label={
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {t("remoteControl")}
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
        description={t("remoteControlDesc")}
        icon={<DeviceMobile />}
      >
        <Toggle value={remoteEnabled} onChange={onToggleRemote} />
      </SettingRow>
      {remoteEnabled && (
        <RemoteControlPanel
          devices={remoteDevices}
          onDevice={onRemoteDevice}
          onPair={onPairDevice}
          trustedIds={remoteTrustedIds}
          onRemember={onRememberDevice}
        />
      )}
    </>
  );
}
