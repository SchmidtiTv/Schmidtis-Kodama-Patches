use tauri::{AppHandle, Manager};

use super::super::model::{PlaybackIntegrationSettings, PlaybackSnapshot, PlaybackStatus};
use crate::discord::DiscordRpc;

#[derive(Default)]
pub(super) struct NowPlayingSync {
    discord_signature: String,
    media_signature: String,
}

impl NowPlayingSync {
    pub(super) fn tick(
        &mut self,
        app: &AppHandle,
        snapshot: &PlaybackSnapshot,
        settings: &PlaybackIntegrationSettings,
    ) {
        self.update_discord(app, snapshot, settings);
        self.update_media(app, snapshot);
    }

    fn update_discord(
        &mut self,
        app: &AppHandle,
        snapshot: &PlaybackSnapshot,
        settings: &PlaybackIntegrationSettings,
    ) {
        let signature = discord_signature(snapshot, settings);
        if signature == self.discord_signature {
            return;
        }
        self.discord_signature = signature;
        let discord = app.state::<DiscordRpc>();
        if !settings.discord_enabled {
            let _ = discord.clear();
            return;
        }
        if settings.hide_discord_while_paused && snapshot.status == PlaybackStatus::Paused {
            let _ = discord.clear();
            return;
        }
        if let Some(track) = snapshot.current_track.as_ref() {
            let _ = discord.update(
                track,
                snapshot.duration_seconds,
                snapshot.position_seconds,
                snapshot.status != PlaybackStatus::Playing,
                &settings.discord_status_display,
            );
        } else {
            let _ = discord.clear();
        }
    }

    fn update_media(&mut self, app: &AppHandle, snapshot: &PlaybackSnapshot) {
        let signature = media_signature(snapshot);
        if signature == self.media_signature {
            return;
        }
        self.media_signature = signature;
        crate::media::update_from_snapshot(app, snapshot);
    }
}

fn discord_signature(
    snapshot: &PlaybackSnapshot,
    settings: &PlaybackIntegrationSettings,
) -> String {
    format!(
        "{}:{}:{}:{}:{}:{}:{}",
        settings.discord_enabled,
        settings.discord_status_display,
        settings.hide_discord_while_paused,
        snapshot
            .current_track
            .as_ref()
            .map(|track| track.video_id.as_str())
            .unwrap_or_default(),
        snapshot
            .current_track
            .as_ref()
            .map(|track| track.title.as_str())
            .unwrap_or_default(),
        snapshot.status == PlaybackStatus::Paused,
        (snapshot.position_seconds / 15.0).floor()
    )
}

fn media_signature(snapshot: &PlaybackSnapshot) -> String {
    format!(
        "{}:{}:{:?}:{}",
        snapshot
            .current_track
            .as_ref()
            .map(|track| track.video_id.as_str())
            .unwrap_or_default(),
        snapshot
            .current_track
            .as_ref()
            .map(|track| format!("{}:{}:{}", track.title, track.album, track.thumbnail))
            .unwrap_or_default(),
        snapshot.status,
        snapshot.position_seconds.floor() as u64 / 5
    )
}
