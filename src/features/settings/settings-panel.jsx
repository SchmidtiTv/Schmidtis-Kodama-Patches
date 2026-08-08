import { useEffect, useRef, useState } from "react";
import {
  ArrowsClockwise,
  Bug,
  ChatText,
  Flask,
  Info,
  Keyboard,
  Link,
  Lock,
  PaintBrushBroad,
  Play,
  PersonArmsSpread,
  ScreencastSimple,
  Translate,
  UserCircle,
  HardDrives,
  WaveformLines,
} from "@/shared/icons/icons.jsx";
import { useAnimations } from "@/features/settings/display-context.jsx";
import { useLang } from "@/shared/i18n/context.jsx";
import { isSettingsSectionLocked } from "./section-store.js";
import { APP_ICON_DEFAULT } from "./settings-constants.js";
import {
  useAppearanceSettings,
  usePlaybackSettings,
  useLyricsSettings,
  useIntegrationSettings,
  useShortcutSettings,
} from "./settings-context.jsx";
import { AccountTabContent } from "./tabs/account-settings-tab.jsx";
import { VisualizerSettingsTab } from "./tabs/visualizer-settings-tab.jsx";
import { AppearanceSettingsTab } from "./tabs/appearance-settings-tab.jsx";
import { SidebarSettingsTab } from "./tabs/sidebar-settings-tab.jsx";
import { PlaybackSettingsTab } from "./tabs/playback-settings-tab.jsx";
import { ConnectionsSettingsTab } from "./tabs/connections-settings-tab.jsx";
import { LyricsSettingsTab } from "./tabs/lyrics-settings-tab.jsx";
import { AccessibilitySettingsTab } from "./tabs/accessibility-settings-tab.jsx";
import { ShortcutsSettingsTab } from "./tabs/shortcuts-settings-tab.jsx";
import { StorageSettingsTab } from "./tabs/storage-settings-tab.jsx";
import { SecuritySettingsTab } from "./tabs/security-settings-tab.jsx";
import { LanguageSettingsTab } from "./tabs/language-settings-tab.jsx";
import { OverlaySettingsTab } from "./tabs/overlay-settings-tab.jsx";
import { ExperimentalSettingsTab } from "./tabs/experimental-settings-tab.jsx";
import { UpdateSettingsTab } from "./tabs/update-settings-tab.jsx";
import { AboutSettingsTab } from "./tabs/about-settings-tab.jsx";
import { DebugSettingsTab } from "./tabs/debug-settings-tab.jsx";
import { useVisualizerSettingsTab } from "./hooks/use-visualizer-settings-tab.js";
import { useSettingsLock } from "./security/use-settings-lock.js";
import { SettingsLockDialogs } from "./security/settings-lock-dialog.jsx";
export function SettingsPanel({
  onOpenOverlayEditor,
  onSectionChange,
  language,
  onLanguageChange,
  updateInfo,
  onCheckUpdate,
  updateDownloading,
  updateDownloadProgress,
  updateDownloaded,
  onDownloadUpdate,
  onInstallUpdate,
  onCancelDownload,
  anonStats,
  onAnonStatsChange,
  hideUserHandle,
  onToggleHideUserHandle,
  tab,
  setTab,
  sidebarCollapsed,
  sidebarWidth,
  sidebarMinWidth,
  sidebarMaxWidth,
  sidebarDefaultWidth,
  onSidebarCollapsedChange,
  onSidebarWidthChange,
}) {
  const anim = useAnimations();
  const t = useLang();
  const {
    accent,
    onAccentChange,
    accentDynamic,
    onAccentDynamicChange,
    accentSat,
    onAccentSatChange,
    accentLight,
    onAccentLightChange,
    appIcon = APP_ICON_DEFAULT,
    appIconCustomizationAvailable,
    onAppIconChange,
    theme,
    onThemeChange,
    animations,
    onAnimationsChange,
    highContrast,
    onToggleHighContrast,
    appFont,
    onAppFontChange,
    appFontScale,
    onFontScaleChange,
    uiZoom,
    onUiZoomChange,
    showTrackNumbers,
    onTrackNumbersChange,
    hideExplicit,
    onHideExplicitChange,
    ambientBackground,
    onToggleAmbientBackground,
    ambientVisualizer,
    onToggleAmbientVisualizer,
    instrumentalViz,
    onToggleInstrumentalViz,
    vizConfig,
    onUpdateViz,
    vizPreviewTrack,
    vizPreviewPlaying,
    playerBarControls,
    onPlayerBarControlToggle,
  } = useAppearanceSettings();
  const {
    autoplay,
    onAutoplayChange,
    crossfade,
    onCrossfadeChange,
    crossfadeOverrides = {},
    crossfadeQueue = [],
    crossfadeDisabled = false,
    onRemoveCrossfadeOverride,
    playbackProgressive,
    onPlaybackProgressiveChange,
    mixTransitionsEnabled,
    onMixTransitionsEnabledChange,
    mixTempoLockEnabled,
    onMixTempoLockEnabledChange,
    videoSyncEnabled,
    onToggleVideoSync,
    videoSyncQuality = "auto",
    onVideoSyncQualityChange,
    videoLyricsStyle = "split",
    onVideoLyricsStyleChange,
  } = usePlaybackSettings();
  const {
    lyricsFontSize,
    onLyricsFontSizeChange,
    lyricsTranslationFontSize,
    onLyricsTranslationFontSizeChange,
    lyricsRomajiFontSize,
    onLyricsRomajiFontSizeChange,
    lyricsProviders,
    onLyricsProvidersChange,
    showRomaji,
    onToggleRomaji,
    showAgentTags,
    onToggleAgentTags,
    syllableZoom,
    onToggleSyllableZoom,
    fluidLyrics,
    onToggleFluidLyrics,
  } = useLyricsSettings();
  const {
    closeTray,
    onCloseTrayChange,
    discordRpc,
    onDiscordRpcChange,
    discordStatusDisplay = "song",
    onDiscordStatusDisplayChange,
    ytmusicHistorySync,
    onYtmusicHistorySyncChange,
    ipv4First,
    onIpv4FirstChange,
    remoteEnabled = false,
    remoteDevices = [],
    remoteTrustedIds = new Set(),
    onToggleRemote,
    onRemoteDevice,
    onRememberDevice,
    onPairDevice,
  } = useIntegrationSettings();
  const {
    customShortcuts,
    shortcutsEnabled,
    recordingShortcut,
    setRecordingShortcut,
    getShortcutParts,
    disableShortcut,
    resetShortcut,
    resetAllShortcuts,
    onShortcutsEnabledChange,
  } = useShortcutSettings();
  // Scroll-spy for the Discord-style sub-nav: watch the [data-settings-section] blocks in the
  // scroll container and report which one sits in the top band as the active section.
  const contentScrollRef = useRef(null);
  useEffect(() => {
    const root = contentScrollRef.current;
    if (!root || !onSectionChange) return;
    const secs = [...root.querySelectorAll("[data-settings-section]")];
    if (!secs.length) {
      onSectionChange(null);
      return;
    }
    const compute = () => {
      if (isSettingsSectionLocked()) return; // don't fight a click's smooth scroll
      // Discord-style proportional "reading line": it sits at the container's top when scrolled to
      // the very top and glides down to the container's bottom as you reach the end of the scroll.
      // The active section is the last one whose top is above that line — so sections light up in
      // order while scrolling and the last one is reached exactly at the bottom (no trailing space).
      const rect = root.getBoundingClientRect();
      const maxScroll = root.scrollHeight - root.clientHeight;
      const progress = maxScroll > 0 ? Math.min(1, root.scrollTop / maxScroll) : 0;
      const line = rect.top + root.clientHeight * progress;
      let active = secs[0];
      for (const s of secs) {
        if (s.getBoundingClientRect().top <= line) active = s;
        else break;
      }
      onSectionChange(active.dataset.settingsSection);
    };
    compute();
    root.addEventListener("scroll", compute, {
      passive: true,
    });
    return () => root.removeEventListener("scroll", compute);
  }, [tab, onSectionChange]);
  // Visualizer preview scales with the window height (live on resize) so on short windows it
  // shrinks — both the box AND the cover — leaving room to reach the options below.
  const {
    vizPreviewOpen,
    toggleVizPreview,
    vizPreviewRef,
    vizScale,
    vizPreviewHReplica,
    vizPreviewCover,
    vizPresets,
    vizPresetName,
    setVizPresetName,
    vizImportRef,
    saveVizPreset,
    applyVizPreset,
    deleteVizPreset,
    exportVizPreset,
    handleVizImport,
  } = useVisualizerSettingsTab({
    t,
    vizConfig,
    onUpdateViz,
  });
  const [debugUnlocked, setDebugUnlocked] = useState(
    () => localStorage.getItem("kiyoshi-debug-unlocked") === "true"
  );
  const [checkingUpdate, setCheckingUpdate] = useState(false);

  // ── PIN protection state ──────────────────────────────────────────────────
  const {
    pinEnabled,
    setPinEnabled,
    pinVerified,
    setPinVerified,
    pinDigits,
    setPinDigits,
    pinError,
    pinShake,
    pinSetup,
    setPinSetup,
    pinSetupDigits,
    setPinSetupDigits,
    pinSetupError,
    setPinSetupError,
    pinType,
    setPinType,
    pinLength,
    setPinLength,
    pinPasswordInput,
    setPinPasswordInput,
    pinSetupPasswordInput,
    setPinSetupPasswordInput,
    showPinPassword,
    setShowPinPassword,
    showSetupPassword,
    setShowSetupPassword,
    pinEmergencyConfirm,
    setPinEmergencyConfirm,
    pinLockTaps,
    setPinLockTaps,
    pinLockTapTimer,
    PIN_EMERGENCY_TAPS,
    PIN_LEN,
    submitPinEntry,
    handlePinKey,
    handleSetupKey,
    advanceSetup,
  } = useSettingsLock(t);
  const navItems = [
    {
      id: "account",
      label: t("account"),
      iconEl: <UserCircle size={18} />,
    },
    {
      id: "darstellung",
      label: t("appearance"),
      iconEl: <PaintBrushBroad size={18} />,
    },
    {
      id: "visualizer",
      label: t("visualizer"),
      iconEl: <WaveformLines size={18} />,
    },
    {
      id: "wiedergabe",
      label: t("playback"),
      iconEl: <Play size={18} />,
    },
    {
      id: "lyrics",
      label: t("lyrics"),
      iconEl: <ChatText size={18} />,
    },
    {
      id: "accessibility",
      label: t("accessibility"),
      iconEl: <PersonArmsSpread size={18} />,
    },
    {
      id: "connections",
      label: t("connections"),
      iconEl: <Link size={18} />,
    },
    {
      id: "shortcuts",
      label: t("shortcuts"),
      iconEl: <Keyboard size={18} />,
    },
    {
      id: "language",
      label: t("language"),
      iconEl: <Translate size={18} />,
    },
    {
      id: "storage",
      label: t("storage"),
      iconEl: <HardDrives size={18} />,
    },
    {
      id: "sicherheit",
      label: t("security"),
      iconEl: <Lock size={18} />,
    },
    {
      id: "overlay",
      label: t("overlay"),
      iconEl: <ScreencastSimple size={18} />,
      badge: "Beta",
    },
    {
      id: "experimental",
      label: t("experimental"),
      iconEl: <Flask size={18} />,
    },
    {
      id: "update",
      label: t("update"),
      iconEl: <ArrowsClockwise size={18} />,
    },
    {
      id: "about",
      label: t("about"),
      iconEl: <Info size={18} />,
    },
    ...(debugUnlocked
      ? [
          {
            id: "debug",
            label: t("debug"),
            iconEl: <Bug size={18} />,
          },
        ]
      : []),
  ];
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        display: "flex",
        overflow: "hidden",
        background: "var(--bg-base)",
      }}
    >
      {/* ── PIN entry overlay ─────────────────────────────────────────────── */}
      <SettingsLockDialogs
        PIN_EMERGENCY_TAPS={PIN_EMERGENCY_TAPS}
        PIN_LEN={PIN_LEN}
        advanceSetup={advanceSetup}
        anim={anim}
        handlePinKey={handlePinKey}
        handleSetupKey={handleSetupKey}
        pinDigits={pinDigits}
        pinEmergencyConfirm={pinEmergencyConfirm}
        pinEnabled={pinEnabled}
        pinError={pinError}
        pinLockTapTimer={pinLockTapTimer}
        pinLockTaps={pinLockTaps}
        pinPasswordInput={pinPasswordInput}
        pinSetup={pinSetup}
        pinSetupDigits={pinSetupDigits}
        pinSetupError={pinSetupError}
        pinSetupPasswordInput={pinSetupPasswordInput}
        pinShake={pinShake}
        pinType={pinType}
        pinVerified={pinVerified}
        setPinDigits={setPinDigits}
        setPinEmergencyConfirm={setPinEmergencyConfirm}
        setPinEnabled={setPinEnabled}
        setPinLockTaps={setPinLockTaps}
        setPinPasswordInput={setPinPasswordInput}
        setPinSetup={setPinSetup}
        setPinSetupDigits={setPinSetupDigits}
        setPinSetupError={setPinSetupError}
        setPinSetupPasswordInput={setPinSetupPasswordInput}
        setPinVerified={setPinVerified}
        setShowPinPassword={setShowPinPassword}
        setShowSetupPassword={setShowSetupPassword}
        showPinPassword={showPinPassword}
        showSetupPassword={showSetupPassword}
        submitPinEntry={submitPinEntry}
        t={t}
      />

      {/* ── PIN setup / change dialog ─────────────────────────────────────── */}

      {/* Right Content */}
      <div
        style={{
          flex: 1,
          background: "var(--bg-base)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "24px max(32px, calc((100% - 760px) / 2)) 0",
            flexShrink: 0,
          }}
        >
          <div
            style={{
              fontSize: "var(--t20)",
              fontWeight: 700,
              marginBottom: 4,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            {navItems.find((i) => i.id === tab)?.label}
            {navItems.find((i) => i.id === tab)?.badge && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  padding: "3px 8px",
                  borderRadius: "var(--r-md)",
                  background: "var(--accent)",
                  color: "#fff",
                  textTransform: "uppercase",
                }}
              >
                {navItems.find((i) => i.id === tab)?.badge}
              </span>
            )}
          </div>
          <div
            style={{
              height: 1,
              background: "var(--border)",
              marginTop: 20,
            }}
          />
        </div>

        <div
          ref={contentScrollRef}
          key={tab}
          className="scrollable"
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "8px max(32px, calc((100% - 760px) / 2)) 32px",
            animation: anim ? "fadeSlideIn 0.22s cubic-bezier(0.4,0,0.2,1)" : "none",
          }}
        >
          {tab === "account" && (
            <AccountTabContent
              hideUserHandle={hideUserHandle}
              onToggleHideUserHandle={onToggleHideUserHandle}
            />
          )}
          {tab === "visualizer" && (
            <VisualizerSettingsTab
              ambientVisualizer={ambientVisualizer}
              applyVizPreset={applyVizPreset}
              deleteVizPreset={deleteVizPreset}
              exportVizPreset={exportVizPreset}
              handleVizImport={handleVizImport}
              instrumentalViz={instrumentalViz}
              onToggleAmbientVisualizer={onToggleAmbientVisualizer}
              onToggleInstrumentalViz={onToggleInstrumentalViz}
              onUpdateViz={onUpdateViz}
              saveVizPreset={saveVizPreset}
              setVizPresetName={setVizPresetName}
              t={t}
              toggleVizPreview={toggleVizPreview}
              vizConfig={vizConfig}
              vizImportRef={vizImportRef}
              vizPresetName={vizPresetName}
              vizPresets={vizPresets}
              vizPreviewCover={vizPreviewCover}
              vizPreviewHReplica={vizPreviewHReplica}
              vizPreviewOpen={vizPreviewOpen}
              vizPreviewPlaying={vizPreviewPlaying}
              vizPreviewRef={vizPreviewRef}
              vizPreviewTrack={vizPreviewTrack}
              vizScale={vizScale}
            />
          )}

          {tab === "darstellung" && (
            <>
              <AppearanceSettingsTab
                accent={accent}
                accentDynamic={accentDynamic}
                accentLight={accentLight}
                accentSat={accentSat}
                anim={anim}
                animations={animations}
                appFontScale={appFontScale}
                appIcon={appIcon}
                appIconCustomizationAvailable={appIconCustomizationAvailable}
                onAccentChange={onAccentChange}
                onAccentDynamicChange={onAccentDynamicChange}
                onAccentLightChange={onAccentLightChange}
                onAccentSatChange={onAccentSatChange}
                onAnimationsChange={onAnimationsChange}
                onAppIconChange={onAppIconChange}
                onFontScaleChange={onFontScaleChange}
                onPlayerBarControlToggle={onPlayerBarControlToggle}
                onThemeChange={onThemeChange}
                onUiZoomChange={onUiZoomChange}
                playerBarControls={playerBarControls}
                t={t}
                theme={theme}
                uiZoom={uiZoom}
                vizPreviewTrack={vizPreviewTrack}
              />
              <SidebarSettingsTab
                collapsed={sidebarCollapsed}
                defaultWidth={sidebarDefaultWidth}
                maxWidth={sidebarMaxWidth}
                minWidth={sidebarMinWidth}
                onCollapsedChange={onSidebarCollapsedChange}
                onWidthChange={onSidebarWidthChange}
                t={t}
                width={sidebarWidth}
              />
            </>
          )}

          {tab === "wiedergabe" && (
            <PlaybackSettingsTab
              anonStats={anonStats}
              autoplay={autoplay}
              crossfade={crossfade}
              crossfadeOverrides={crossfadeOverrides}
              crossfadeQueue={crossfadeQueue}
              crossfadeDisabled={crossfadeDisabled}
              hideExplicit={hideExplicit}
              onAnonStatsChange={onAnonStatsChange}
              onAutoplayChange={onAutoplayChange}
              onCrossfadeChange={onCrossfadeChange}
              onHideExplicitChange={onHideExplicitChange}
              onPlaybackProgressiveChange={onPlaybackProgressiveChange}
              mixTransitionsEnabled={mixTransitionsEnabled}
              onMixTransitionsEnabledChange={onMixTransitionsEnabledChange}
              mixTempoLockEnabled={mixTempoLockEnabled}
              onMixTempoLockEnabledChange={onMixTempoLockEnabledChange}
              onRemoveCrossfadeOverride={onRemoveCrossfadeOverride}
              onTrackNumbersChange={onTrackNumbersChange}
              playbackProgressive={playbackProgressive}
              showTrackNumbers={showTrackNumbers}
              t={t}
            />
          )}

          {tab === "connections" && (
            <ConnectionsSettingsTab
              discordRpc={discordRpc}
              discordStatusDisplay={discordStatusDisplay}
              ipv4First={ipv4First}
              onDiscordRpcChange={onDiscordRpcChange}
              onDiscordStatusDisplayChange={onDiscordStatusDisplayChange}
              onIpv4FirstChange={onIpv4FirstChange}
              onPairDevice={onPairDevice}
              onRememberDevice={onRememberDevice}
              onRemoteDevice={onRemoteDevice}
              onToggleRemote={onToggleRemote}
              onYtmusicHistorySyncChange={onYtmusicHistorySyncChange}
              remoteDevices={remoteDevices}
              remoteEnabled={remoteEnabled}
              remoteTrustedIds={remoteTrustedIds}
              t={t}
              ytmusicHistorySync={ytmusicHistorySync}
            />
          )}

          {tab === "lyrics" && (
            <LyricsSettingsTab
              fluidLyrics={fluidLyrics}
              lyricsFontSize={lyricsFontSize}
              lyricsProviders={lyricsProviders}
              lyricsRomajiFontSize={lyricsRomajiFontSize}
              lyricsTranslationFontSize={lyricsTranslationFontSize}
              onLyricsFontSizeChange={onLyricsFontSizeChange}
              onLyricsProvidersChange={onLyricsProvidersChange}
              onLyricsRomajiFontSizeChange={onLyricsRomajiFontSizeChange}
              onLyricsTranslationFontSizeChange={onLyricsTranslationFontSizeChange}
              onToggleAgentTags={onToggleAgentTags}
              onToggleFluidLyrics={onToggleFluidLyrics}
              onToggleRomaji={onToggleRomaji}
              onToggleSyllableZoom={onToggleSyllableZoom}
              showAgentTags={showAgentTags}
              showRomaji={showRomaji}
              syllableZoom={syllableZoom}
              t={t}
            />
          )}

          {tab === "accessibility" && (
            <AccessibilitySettingsTab
              ambientBackground={ambientBackground}
              appFont={appFont}
              closeTray={closeTray}
              highContrast={highContrast}
              language={language}
              onAppFontChange={onAppFontChange}
              onCloseTrayChange={onCloseTrayChange}
              onToggleAmbientBackground={onToggleAmbientBackground}
              onToggleHighContrast={onToggleHighContrast}
              t={t}
            />
          )}

          {tab === "shortcuts" && (
            <ShortcutsSettingsTab
              customShortcuts={customShortcuts}
              shortcutsEnabled={shortcutsEnabled}
              getShortcutParts={getShortcutParts}
              disableShortcut={disableShortcut}
              onResetShortcuts={resetAllShortcuts}
              onShortcutsEnabledChange={onShortcutsEnabledChange}
              recordingShortcut={recordingShortcut}
              resetShortcut={resetShortcut}
              setRecordingShortcut={setRecordingShortcut}
              t={t}
            />
          )}

          {tab === "storage" && <StorageSettingsTab t={t} />}

          {tab === "sicherheit" && (
            <SecuritySettingsTab
              pinEmergencyConfirm={pinEmergencyConfirm}
              pinEnabled={pinEnabled}
              pinLength={pinLength}
              pinType={pinType}
              setPinDigits={setPinDigits}
              setPinEmergencyConfirm={setPinEmergencyConfirm}
              setPinEnabled={setPinEnabled}
              setPinLength={setPinLength}
              setPinPasswordInput={setPinPasswordInput}
              setPinSetup={setPinSetup}
              setPinSetupDigits={setPinSetupDigits}
              setPinSetupError={setPinSetupError}
              setPinSetupPasswordInput={setPinSetupPasswordInput}
              setPinType={setPinType}
              setPinVerified={setPinVerified}
              t={t}
            />
          )}

          {tab === "language" && (
            <LanguageSettingsTab language={language} onLanguageChange={onLanguageChange} t={t} />
          )}

          {tab === "overlay" && (
            <OverlaySettingsTab onOpenOverlayEditor={onOpenOverlayEditor} t={t} />
          )}

          {tab === "experimental" && (
            <ExperimentalSettingsTab
              onToggleVideoSync={onToggleVideoSync}
              onVideoLyricsStyleChange={onVideoLyricsStyleChange}
              onVideoSyncQualityChange={onVideoSyncQualityChange}
              t={t}
              videoLyricsStyle={videoLyricsStyle}
              videoSyncEnabled={videoSyncEnabled}
              videoSyncQuality={videoSyncQuality}
            />
          )}

          {tab === "update" && (
            <UpdateSettingsTab
              checkingUpdate={checkingUpdate}
              onCancelDownload={onCancelDownload}
              onCheckUpdate={onCheckUpdate}
              onDownloadUpdate={onDownloadUpdate}
              onInstallUpdate={onInstallUpdate}
              setCheckingUpdate={setCheckingUpdate}
              t={t}
              updateDownloadProgress={updateDownloadProgress}
              updateDownloaded={updateDownloaded}
              updateDownloading={updateDownloading}
              updateInfo={updateInfo}
            />
          )}

          {tab === "about" && <AboutSettingsTab t={t} />}

          {tab === "debug" && (
            <DebugSettingsTab setDebugUnlocked={setDebugUnlocked} setTab={setTab} t={t} />
          )}
        </div>
      </div>
    </div>
  );
}
