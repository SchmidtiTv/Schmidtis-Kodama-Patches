use super::model::{
    PlaybackIntegrationSettings, PlaybackSnapshot, PlaybackStatus, PlaybackTrack, RepeatMode,
    TransitionPolicyUpdate, TransportUpdate,
};
use super::state::PlaybackEngine;
use crate::audio::player::{AudioCmd, AudioPlayer};
use tauri::Emitter;

#[tauri::command]
pub fn player_get_snapshot(
    state: tauri::State<'_, PlaybackEngine>,
) -> Result<PlaybackSnapshot, String> {
    state.snapshot()
}

#[tauri::command]
pub fn player_set_ui_visible(
    state: tauri::State<'_, PlaybackEngine>,
    visible: bool,
) -> Result<PlaybackSnapshot, String> {
    state.set_ui_visible(visible);
    state.snapshot()
}

#[tauri::command]
pub fn player_update_integrations(
    state: tauri::State<'_, PlaybackEngine>,
    settings: PlaybackIntegrationSettings,
) -> Result<PlaybackSnapshot, String> {
    state.update_integration_settings(settings)
}

#[tauri::command]
pub fn player_set_liked(
    state: tauri::State<'_, PlaybackEngine>,
    liked: bool,
) -> Result<PlaybackSnapshot, String> {
    state.set_current_track_liked(liked)
}

#[tauri::command]
pub fn player_set_queue(
    app: tauri::AppHandle,
    state: tauri::State<'_, PlaybackEngine>,
    queue: Vec<PlaybackTrack>,
) -> Result<PlaybackSnapshot, String> {
    state.require_local_transport()?;
    let snapshot = state.replace_queue(queue)?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_play(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    let sender = audio.sender()?;
    let current = engine.snapshot()?;
    match current.status {
        PlaybackStatus::Playing => return Ok(current),
        PlaybackStatus::Paused => {
            sender
                .send(AudioCmd::Resume)
                .map_err(|error| error.to_string())?;
            // Only the audio thread knows whether a live sink can be resumed. It emits the
            // resulting Playing/Loading snapshot, or restarts the selected track when needed.
            engine.snapshot()
        }
        PlaybackStatus::Loading | PlaybackStatus::Stopped => {
            let request = engine
                .restart_current()?
                .ok_or_else(|| "cannot play without a current track".to_string())?;
            sender
                .send(AudioCmd::PlayResolved {
                    request: request.clone(),
                })
                .map_err(|error| error.to_string())?;
            emit_track_changed(&app, &request.track, "play");
            let snapshot = engine.snapshot()?;
            emit_snapshot(&app, &snapshot);
            Ok(snapshot)
        }
    }
}

#[tauri::command]
pub fn player_restart(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    let request = engine
        .restart_current()?
        .ok_or_else(|| "cannot restart without a current track".to_string())?;
    audio
        .sender()?
        .send(AudioCmd::PlayResolved {
            request: request.clone(),
        })
        .map_err(|error| error.to_string())?;
    emit_track_changed(&app, &request.track, "restart");
    let snapshot = engine.snapshot()?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_preload(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    // Resolve and construct the selected source while keeping transport paused.
    // This is used only for the restored startup selection, so reopening the app
    // makes Play instant without unexpectedly starting audio.
    let request = engine
        .restart_current()?
        .ok_or_else(|| "cannot preload without a current track".to_string())?;
    let snapshot = engine.update_transport(TransportUpdate {
        status: Some(PlaybackStatus::Paused),
        ..TransportUpdate::default()
    })?;
    audio
        .sender()?
        .send(AudioCmd::PlayResolved { request })
        .map_err(|error| error.to_string())?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_pause(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    if engine.snapshot()?.status == PlaybackStatus::Stopped {
        return engine.snapshot();
    }
    let snapshot = engine.update_transport(TransportUpdate {
        status: Some(PlaybackStatus::Paused),
        ..TransportUpdate::default()
    })?;
    audio
        .sender()?
        .send(AudioCmd::Pause)
        .map_err(|error| error.to_string())?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_next(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    let sender = audio.sender()?;
    let Some(request) = engine.select_next()? else {
        return engine.snapshot();
    };
    sender
        .send(AudioCmd::PlayResolved {
            request: request.clone(),
        })
        .map_err(|error| error.to_string())?;
    emit_track_changed(&app, &request.track, "next");
    let snapshot = engine.snapshot()?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_previous(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    let sender = audio.sender()?;
    let Some(request) = engine.select_previous()? else {
        return engine.snapshot();
    };
    sender
        .send(AudioCmd::PlayResolved {
            request: request.clone(),
        })
        .map_err(|error| error.to_string())?;
    emit_track_changed(&app, &request.track, "previous");
    let snapshot = engine.snapshot()?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_seek(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
    position: f64,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    let current = engine.snapshot()?;
    let position = if current.duration_seconds > 0.0 {
        position.min(current.duration_seconds)
    } else {
        position
    };
    let snapshot = engine.update_transport(TransportUpdate {
        position_seconds: Some(position),
        ..TransportUpdate::default()
    })?;
    audio
        .sender()?
        .send(AudioCmd::Seek(position))
        .map_err(|error| error.to_string())?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_set_volume(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
    volume: f32,
) -> Result<PlaybackSnapshot, String> {
    let snapshot = engine.update_transport(TransportUpdate {
        volume: Some(volume),
        ..TransportUpdate::default()
    })?;
    audio
        .sender()?
        .send(AudioCmd::SetVolume(volume * volume))
        .map_err(|error| error.to_string())?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_set_shuffle(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    shuffle: bool,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    let snapshot = engine.update_transport(TransportUpdate {
        shuffle: Some(shuffle),
        ..TransportUpdate::default()
    })?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_set_repeat(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    repeat: RepeatMode,
) -> Result<PlaybackSnapshot, String> {
    engine.require_local_transport()?;
    let snapshot = engine.update_transport(TransportUpdate {
        repeat: Some(repeat),
        ..TransportUpdate::default()
    })?;
    emit_snapshot(&app, &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn playback_engine_snapshot(
    state: tauri::State<'_, PlaybackEngine>,
) -> Result<PlaybackSnapshot, String> {
    state.snapshot()
}

#[tauri::command]
pub fn playback_engine_replace_queue(
    state: tauri::State<'_, PlaybackEngine>,
    queue: Vec<PlaybackTrack>,
) -> Result<PlaybackSnapshot, String> {
    state.replace_queue(queue)
}

#[tauri::command]
pub fn playback_engine_set_current_track(
    state: tauri::State<'_, PlaybackEngine>,
    track: Option<PlaybackTrack>,
) -> Result<PlaybackSnapshot, String> {
    state.require_local_transport()?;
    state.set_current_track(track)
}

#[tauri::command]
pub fn playback_engine_update_transport(
    state: tauri::State<'_, PlaybackEngine>,
    update: TransportUpdate,
) -> Result<PlaybackSnapshot, String> {
    if update.status.is_some()
        || update.position_seconds.is_some()
        || update.shuffle.is_some()
        || update.repeat.is_some()
    {
        state.require_local_transport()?;
    }
    state.update_transport(update)
}

#[tauri::command]
pub fn playback_engine_update_transition_policy(
    state: tauri::State<'_, PlaybackEngine>,
    update: TransitionPolicyUpdate,
) -> Result<PlaybackSnapshot, String> {
    state.update_transition_policy(update)
}

fn emit_snapshot(app: &tauri::AppHandle, snapshot: &PlaybackSnapshot) {
    let _ = app.emit("playback-state-changed", snapshot);
}

fn emit_track_changed(app: &tauri::AppHandle, track: &PlaybackTrack, reason: &str) {
    let _ = app.emit(
        "playback-track-changed",
        serde_json::json!({ "track": track, "reason": reason }),
    );
}
