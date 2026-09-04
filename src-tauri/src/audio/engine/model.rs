use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlaybackTrack {
    pub video_id: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub artists: Vec<String>,
    #[serde(default)]
    pub album: String,
    #[serde(default)]
    pub thumbnail: String,
    #[serde(default)]
    pub duration_seconds: Option<f64>,
}

impl PlaybackTrack {
    pub(super) fn normalize(mut self) -> Result<Self, String> {
        self.video_id = self.video_id.trim().to_string();
        validate_video_id("videoId", &self.video_id)?;
        if self
            .duration_seconds
            .is_some_and(|duration| !duration.is_finite() || duration < 0.0)
        {
            return Err("track durationSeconds must be finite and non-negative".to_string());
        }
        Ok(self)
    }
}

#[derive(Clone, Copy, Debug, Default, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum PlaybackStatus {
    #[default]
    Stopped,
    Loading,
    Playing,
    Paused,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum RepeatMode {
    #[default]
    None,
    All,
    One,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlaybackSnapshot {
    pub current_track: Option<PlaybackTrack>,
    pub queue: Vec<PlaybackTrack>,
    pub status: PlaybackStatus,
    pub position_seconds: f64,
    pub duration_seconds: f64,
    pub volume: f32,
    pub shuffle: bool,
    pub repeat: RepeatMode,
    pub playback_instance: u64,
    pub revision: u64,
}

impl Default for PlaybackSnapshot {
    fn default() -> Self {
        Self {
            current_track: None,
            queue: Vec::new(),
            status: PlaybackStatus::Stopped,
            position_seconds: 0.0,
            duration_seconds: 0.0,
            volume: 0.4,
            shuffle: false,
            repeat: RepeatMode::None,
            playback_instance: 0,
            revision: 0,
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TransportUpdate {
    pub status: Option<PlaybackStatus>,
    pub position_seconds: Option<f64>,
    pub duration_seconds: Option<f64>,
    pub volume: Option<f32>,
    pub shuffle: Option<bool>,
    pub repeat: Option<RepeatMode>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CrossfadeOverride {
    pub from_video_id: String,
    pub to_video_id: String,
    pub seconds: f64,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum MixPreset {
    Auto,
    Fade,
    Rise,
    Blend,
    Wave,
    Melt,
    Slam,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum MixVolumeCurve {
    Smooth,
    Overlap,
    Cut,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum MixEqCurve {
    CenterBass,
    EndBassSwap,
    ThreeBandFade,
    None,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum MixEffect {
    None,
    LowPass,
    HighPass,
}

/// A Mix setting resolved to an actual queue pair. Track-instance identifiers stay in the
/// playlist configuration; only native-safe video identifiers cross the Tauri boundary.
#[derive(Clone, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct MixTransition {
    pub from_video_id: String,
    pub to_video_id: String,
    pub preset: MixPreset,
    pub bars: u8,
    pub volume_curve: MixVolumeCurve,
    pub eq_curve: MixEqCurve,
    pub effect: MixEffect,
    pub beat_offset_ms: f64,
    #[serde(default)]
    pub from_bpm: Option<f32>,
    #[serde(default)]
    pub to_bpm: Option<f32>,
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TransitionPolicyUpdate {
    pub crossfade_seconds: Option<f64>,
    pub crossfade_overrides: Option<Vec<CrossfadeOverride>>,
    pub progressive: Option<bool>,
    pub automatic_crossfade: Option<bool>,
    pub mix_transitions: Option<Vec<MixTransition>>,
    pub mix_enabled: Option<bool>,
    pub mix_tempo_lock: Option<bool>,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PlaybackIntegrationSettings {
    #[serde(default)]
    pub discord_enabled: bool,
    #[serde(default = "default_discord_status_display")]
    pub discord_status_display: String,
    #[serde(default = "default_hide_discord_while_paused")]
    pub hide_discord_while_paused: bool,
    #[serde(default)]
    pub lastfm_connected: bool,
    #[serde(default)]
    pub youtube_history_enabled: bool,
    #[serde(default)]
    pub overlay_updates_enabled: bool,
    #[serde(default)]
    pub remote_enabled: bool,
}

impl Default for PlaybackIntegrationSettings {
    fn default() -> Self {
        Self {
            discord_enabled: false,
            discord_status_display: default_discord_status_display(),
            hide_discord_while_paused: default_hide_discord_while_paused(),
            lastfm_connected: false,
            youtube_history_enabled: false,
            overlay_updates_enabled: false,
            remote_enabled: false,
        }
    }
}

impl PlaybackIntegrationSettings {
    pub(super) fn normalize(mut self) -> Result<Self, String> {
        if !matches!(
            self.discord_status_display.as_str(),
            "song" | "artist" | "app"
        ) {
            return Err("discordStatusDisplay must be 'song', 'artist', or 'app'".to_string());
        }
        self.discord_status_display = self.discord_status_display.trim().to_string();
        Ok(self)
    }
}

fn default_discord_status_display() -> String {
    "song".to_string()
}

fn default_hide_discord_while_paused() -> bool {
    true
}

#[derive(Clone, Debug, PartialEq)]
pub struct PlaybackSourceRequest {
    pub track: PlaybackTrack,
    pub progressive: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct CrossfadeRequest {
    pub from_track: PlaybackTrack,
    pub to_track: PlaybackTrack,
    pub seconds: f64,
    pub progressive: bool,
    /// Mix policy is carried with the prepared pair for the future DSP mixer. It does not alter
    /// the current crossfade renderer yet.
    pub mix_transition: Option<MixTransition>,
    pub mix_tempo_lock: bool,
}

pub(super) fn validate_seconds(name: &str, value: Option<f64>) -> Result<(), String> {
    if value.is_some_and(|seconds| !seconds.is_finite() || seconds < 0.0) {
        return Err(format!("{name} must be finite and non-negative"));
    }
    Ok(())
}

pub(super) fn validate_video_id(name: &str, video_id: &str) -> Result<(), String> {
    if video_id.is_empty()
        || !video_id
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '_'))
    {
        return Err(format!(
            "{name} must contain only letters, numbers, '-' or '_'"
        ));
    }
    Ok(())
}
