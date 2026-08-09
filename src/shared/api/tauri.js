// The sole frontend boundary for Tauri Rust commands. Keep command names here so
// feature code depends on a descriptive JavaScript API rather than IPC strings.
async function invoke(command, args) {
  const { invoke: invokeCommand } = await import("@tauri-apps/api/core");
  return invokeCommand(command, args);
}

// Needed by the browser-E2E media recorder; command strings remain owned here.
export const nativeCommand = {
  audioPlay: "audio_play",
  audioPause: "audio_pause",
  audioResume: "audio_resume",
  audioSeek: "audio_seek",
  setAudioVolume: "audio_set_volume",
};

export const native = {
  /** @param {boolean} fullscreen @returns {Promise<void>} @example await native.setFullscreen(true) */
  setFullscreen: (fullscreen) => invoke("set_fullscreen", { fullscreen }),
  /** @param {{profileName: string, confirmLabel: string, switchHint: string}} args @returns {Promise<void>} @example await native.openLoginWindow({ profileName: "default", confirmLabel: "Use account", switchHint: "Switch" }) */
  openLoginWindow: (args) => invoke("open_login_window", args),
  /** @returns {Promise<void>} @example await native.closeLoginWindow() */
  closeLoginWindow: () => invoke("close_login_window"),
  /** @param {string | null} videoId @param {Record<string, string>} overrides @returns {Promise<void>} @example await native.openComposerWindow("dQw4w9WgXcQ", {}) */
  openComposerWindow: (videoId, overrides) =>
    invoke("open_composer_window", { videoId: videoId || null, overrides }),
  /** @param {string} label @returns {Promise<void>} @example await native.removeWindowBorderFor("overlay-editor") */
  removeWindowBorderFor: (label) => invoke("remove_window_border_for", { label }),
  /** @param {string} label @returns {Promise<void>} @example await native.lockSquareFor("mini-player") */
  lockSquareFor: (label) => invoke("lock_square_for", { label }),
  /** @returns {Promise<void>} @example await native.clearDiscordRpc() */
  clearDiscordRpc: () => invoke("clear_discord_rpc"),
  /** @param {string} file @returns {Promise<void>} @example await native.setAppIcon("forest.png") */
  setAppIcon: (file) => invoke("set_app_icon", { file }),
  /** @returns {Promise<boolean>} Whether this build supports selecting a runtime app icon. */
  appIconCustomizationAvailable: () => invoke("app_icon_customization_available"),
  /** @returns {Promise<void>} Opens the cache root in the platform file manager. @example await native.openCacheDirectory() */
  openCacheDirectory: () => invoke("open_cache_directory"),

  /** @param {string} url @param {number} seekTo @returns {Promise<void>} @example await native.audioPlay("http://localhost:9847/audio", 0) */
  audioPlay: (url, seekTo) => invoke("audio_play", { url, seekTo }),
  /** @returns {Promise<void>} @example await native.audioPause() */
  audioPause: () => invoke("audio_pause"),
  /** @returns {Promise<void>} @example await native.audioResume() */
  audioResume: () => invoke("audio_resume"),
  /** @param {number} position @returns {Promise<void>} @example await native.audioSeek(42.5) */
  audioSeek: (position) => invoke("audio_seek", { position }),
  /** @param {boolean} enabled @returns {Promise<void>} @example await native.setAudioAnalysisEnabled(true) */
  setAudioAnalysisEnabled: (enabled) => invoke("audio_set_analysis_enabled", { enabled }),
  /** @param {number} volume @returns {Promise<void>} @example await native.setAudioVolume(0.5) */
  setAudioVolume: (volume) => invoke("audio_set_volume", { volume }),

  /** @returns {Promise<object>} Playback snapshot. @example const snapshot = await native.getPlayerSnapshot() */
  getPlayerSnapshot: () => invoke("player_get_snapshot"),
  /** @param {boolean} visible @returns {Promise<object>} Playback snapshot. @example await native.setPlayerUiVisible(false) */
  setPlayerUiVisible: (visible) => invoke("player_set_ui_visible", { visible }),
  /** @param {boolean} liked @returns {Promise<object>} Playback snapshot. @example await native.setPlayerLiked(true) */
  setPlayerLiked: (liked) => invoke("player_set_liked", { liked }),
  /** @param {object} settings @returns {Promise<object>} Playback snapshot. @example await native.updatePlayerIntegrations({ discordEnabled: true }) */
  updatePlayerIntegrations: (settings) => invoke("player_update_integrations", { settings }),
  /** @param {object[]} queue @returns {Promise<object>} Playback snapshot. @example await native.replacePlaybackQueue([]) */
  replacePlaybackQueue: (queue) => invoke("playback_engine_replace_queue", { queue }),
  /** @param {object | null} track @returns {Promise<object>} Playback snapshot. @example await native.setPlaybackCurrentTrack(null) */
  setPlaybackCurrentTrack: (track) => invoke("playback_engine_set_current_track", { track }),
  /** @param {object} update @returns {Promise<object>} Playback snapshot. @example await native.updatePlaybackTransport({ volume: 0.5 }) */
  updatePlaybackTransport: (update) => invoke("playback_engine_update_transport", { update }),
  /** @param {object} update @returns {Promise<object>} Playback snapshot. @example await native.updatePlaybackTransitionPolicy({ crossfadeSeconds: 3 }) */
  updatePlaybackTransitionPolicy: (update) =>
    invoke("playback_engine_update_transition_policy", { update }),
  /** @returns {Promise<object>} Playback snapshot. @example await native.playerPlay() */
  playerPlay: () => invoke("player_play"),
  /** @returns {Promise<object>} Playback snapshot. @example await native.playerRestart() */
  playerRestart: () => invoke("player_restart"),
  /** @returns {Promise<object>} Playback snapshot. @example await native.playerPreload() */
  playerPreload: () => invoke("player_preload"),
  /** @returns {Promise<object>} Playback snapshot. @example await native.playerPause() */
  playerPause: () => invoke("player_pause"),
  /** @returns {Promise<object>} Playback snapshot. @example await native.playerNext() */
  playerNext: () => invoke("player_next"),
  /** @returns {Promise<object>} Playback snapshot. @example await native.playerPrevious() */
  playerPrevious: () => invoke("player_previous"),
  /** @param {number} position @returns {Promise<object>} Playback snapshot. @example await native.playerSeek(42.5) */
  playerSeek: (position) => invoke("player_seek", { position }),
  /** @param {number} volume @returns {Promise<object>} Playback snapshot. @example await native.setPlayerVolume(0.5) */
  setPlayerVolume: (volume) => invoke("player_set_volume", { volume }),
  /** @param {boolean} shuffle @returns {Promise<object>} Playback snapshot. @example await native.setPlayerShuffle(true) */
  setPlayerShuffle: (shuffle) => invoke("player_set_shuffle", { shuffle }),
  /** @param {"none" | "one" | "all"} repeat @returns {Promise<object>} Playback snapshot. @example await native.setPlayerRepeat("all") */
  setPlayerRepeat: (repeat) => invoke("player_set_repeat", { repeat }),

  /** @returns {Promise<void>} @example await native.relaunchApp() */
  relaunchApp: () => invoke("relaunch_app"),
  /** @returns {Promise<void>} @example await native.quitApp() */
  quitApp: () => invoke("quit_app"),
  /** @returns {Promise<void>} @example await native.stopServer() */
  stopServer: () => invoke("stop_server_cmd"),
  /** @param {string} showLabel @param {string} quitLabel @returns {Promise<void>} @example await native.updateTrayLabels("Show", "Quit") */
  updateTrayLabels: (showLabel, quitLabel) =>
    invoke("update_tray_labels", { showLabel, quitLabel }),
  /** @param {boolean} enabled @returns {Promise<void>} @example await native.setCloseToTray(true) */
  setCloseToTray: (enabled) => invoke("set_close_to_tray", { enabled }),
  /** @returns {Promise<string>} Base64 PNG screenshot. @example const png = await native.captureScreenshot() */
  captureScreenshot: () => invoke("capture_screenshot"),
  /** @param {string} profileName @returns {Promise<void>} @example await native.ensureSessionKeeper("default") */
  ensureSessionKeeper: (profileName) => invoke("ensure_session_keeper", { profileName }),
  /** @param {string} profileName @returns {Promise<boolean>} Whether a SIDTS cookie was captured. @example const rotated = await native.rotateSessionCookies("default") */
  rotateSessionCookies: (profileName) => invoke("rotate_session_cookies", { profileName }),
  /** @returns {Promise<void>} @example await native.stopSessionKeeper() */
  stopSessionKeeper: () => invoke("stop_session_keeper"),
};
