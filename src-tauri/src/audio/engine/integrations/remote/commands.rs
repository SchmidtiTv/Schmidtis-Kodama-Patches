use reqwest::blocking::Client;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter};

use super::super::super::model::{
    PlaybackSourceRequest, PlaybackStatus, RepeatMode, TransportUpdate,
};
use super::super::super::PlaybackEngine;
use super::super::http::{artists, post_lastfm, unix_timestamp, API_ROOT};
use crate::audio::player::AudioCmd;

pub(super) fn run(
    command: &Value,
    client: &Client,
    app: &AppHandle,
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
) -> Result<(), String> {
    let action = command
        .get("action")
        .and_then(Value::as_str)
        .unwrap_or_default();
    if matches!(
        action,
        "playpause" | "next" | "prev" | "shuffle" | "repeat" | "seek" | "queueJump"
    ) {
        engine.require_local_transport()?;
    }
    match action {
        "playpause" => toggle_playback(engine, audio_tx, app)?,
        "next" => play_request(engine.select_next()?, "remoteNext", app, audio_tx)?,
        "prev" => play_request(engine.select_previous()?, "remotePrevious", app, audio_tx)?,
        "shuffle" => toggle_shuffle(engine)?,
        "repeat" => cycle_repeat(engine)?,
        "seek" => seek(command, engine, audio_tx)?,
        "volume" => set_volume(command, engine, audio_tx)?,
        "queueJump" => jump_queue(command, engine, audio_tx, app)?,
        "like" => toggle_like(client, app, engine)?,
        _ => {}
    }
    let _ = app.emit("playback-state-changed", engine.snapshot()?);
    Ok(())
}

fn toggle_playback(
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    app: &AppHandle,
) -> Result<(), String> {
    match engine.snapshot()?.status {
        PlaybackStatus::Playing | PlaybackStatus::Loading => {
            engine.update_transport(TransportUpdate {
                status: Some(PlaybackStatus::Paused),
                ..TransportUpdate::default()
            })?;
            send_audio(audio_tx, AudioCmd::Pause)?;
        }
        PlaybackStatus::Paused => {
            send_audio(audio_tx, AudioCmd::Resume)?;
        }
        PlaybackStatus::Stopped => {
            play_request(engine.restart_current()?, "remotePlay", app, audio_tx)?;
        }
    }
    Ok(())
}

fn toggle_shuffle(engine: &PlaybackEngine) -> Result<(), String> {
    let snapshot = engine.snapshot()?;
    engine.update_transport(TransportUpdate {
        shuffle: Some(!snapshot.shuffle),
        ..TransportUpdate::default()
    })?;
    Ok(())
}

fn cycle_repeat(engine: &PlaybackEngine) -> Result<(), String> {
    let repeat = match engine.snapshot()?.repeat {
        RepeatMode::None => RepeatMode::All,
        RepeatMode::All => RepeatMode::One,
        RepeatMode::One => RepeatMode::None,
    };
    engine.update_transport(TransportUpdate {
        repeat: Some(repeat),
        ..TransportUpdate::default()
    })?;
    Ok(())
}

fn seek(
    command: &Value,
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
) -> Result<(), String> {
    let Some(position) = command.get("position").and_then(Value::as_f64) else {
        return Ok(());
    };
    let snapshot = engine.snapshot()?;
    let position = if snapshot.duration_seconds > 0.0 {
        position.clamp(0.0, snapshot.duration_seconds)
    } else {
        position.max(0.0)
    };
    engine.update_transport(TransportUpdate {
        position_seconds: Some(position),
        ..TransportUpdate::default()
    })?;
    send_audio(audio_tx, AudioCmd::Seek(position))
}

fn set_volume(
    command: &Value,
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
) -> Result<(), String> {
    let Some(percent) = command.get("value").and_then(Value::as_f64) else {
        return Ok(());
    };
    let volume = (percent / 100.0).clamp(0.0, 1.0) as f32;
    engine.update_transport(TransportUpdate {
        volume: Some(volume),
        ..TransportUpdate::default()
    })?;
    send_audio(audio_tx, AudioCmd::SetVolume(volume * volume))
}

fn jump_queue(
    command: &Value,
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    app: &AppHandle,
) -> Result<(), String> {
    let Some(video_id) = command.get("videoId").and_then(Value::as_str) else {
        return Ok(());
    };
    play_request(
        engine.select_track(video_id)?,
        "remoteQueueJump",
        app,
        audio_tx,
    )
}

fn toggle_like(client: &Client, app: &AppHandle, engine: &PlaybackEngine) -> Result<(), String> {
    let snapshot = engine.snapshot()?;
    let Some(track) = snapshot.current_track.as_ref() else {
        return Ok(());
    };
    let liked = !engine.current_track_liked()?;
    let rating = if liked { "LIKE" } else { "INDIFFERENT" };
    let response = client
        .post(format!("{API_ROOT}/like/{}", track.video_id))
        .json(&json!({
            "rating": rating,
            "title": track.title,
            "artists": artists(track),
            "album": track.album,
            "thumbnail": track.thumbnail,
            "duration": track.duration_seconds.unwrap_or_default(),
        }))
        .send()
        .map_err(|error| error.to_string())?;
    if response.status().is_success() {
        engine.set_current_track_liked(liked)?;
        let lastfm_action = if liked { "love" } else { "unlove" };
        if engine.integration_settings()?.lastfm_connected {
            post_lastfm(client, lastfm_action, track, unix_timestamp());
        }
        let _ = app.emit(
            "playback-liked-changed",
            json!({ "videoId": track.video_id, "liked": liked }),
        );
    }
    Ok(())
}

fn play_request(
    request: Option<PlaybackSourceRequest>,
    reason: &str,
    app: &AppHandle,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
) -> Result<(), String> {
    if let Some(request) = request {
        let track = request.track.clone();
        send_audio(audio_tx, AudioCmd::PlayResolved { request })?;
        let _ = app.emit(
            "playback-track-changed",
            json!({ "track": track, "reason": reason }),
        );
    }
    Ok(())
}

fn send_audio(
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    command: AudioCmd,
) -> Result<(), String> {
    audio_tx.send(command).map_err(|error| error.to_string())
}
