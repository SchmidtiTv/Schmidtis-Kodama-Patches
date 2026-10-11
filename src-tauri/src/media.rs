// OS media controls via `souvlaki`: Windows SMTC (the volume-flyout media tile, lock screen,
// keyboard media keys), macOS Now Playing / MPRemoteCommandCenter, Linux MPRIS.
//
// souvlaki's MediaControls is platform-bound and not Send/Sync (COM on Windows, AppKit on
// macOS must be the main thread), so we keep it in a main-thread thread-local and only ever
// touch it from the main thread (commands marshal via AppHandle::run_on_main_thread).
use std::cell::RefCell;
use std::time::Duration;

use souvlaki::{
    MediaControlEvent, MediaControls, MediaMetadata, MediaPlayback, MediaPosition, PlatformConfig,
    SeekDirection,
};
use tauri::{AppHandle, Emitter};

use crate::audio::engine::{PlaybackSourceRequest, PlaybackStatus, TransportUpdate};
use crate::audio::player::AudioCmd;
use crate::audio::PlaybackEngine;

thread_local! {
    static CONTROLS: RefCell<Option<MediaControls>> = const { RefCell::new(None) };
    // Signature of the metadata last pushed to the OS. The frontend refreshes every ~15s to
    // keep the elapsed time accurate, but on Windows `set_metadata` re-uploads the cover to
    // SMTC (WinRT/COM work on the UI thread) and janks a frame. We skip it when the metadata
    // is unchanged and only update playback state/position — which is cheap.
    static LAST_META: RefCell<Option<String>> = const { RefCell::new(None) };
}

/// Create the OS media controls and route button presses directly into the native
/// playback engine. MUST be called on the main thread (call from setup()).
pub fn init(
    app: &AppHandle,
    engine: PlaybackEngine,
    audio_tx: std::sync::mpsc::SyncSender<AudioCmd>,
) {
    #[cfg(target_os = "windows")]
    let hwnd: Option<*mut std::ffi::c_void> = app
        .get_webview_window("main")
        .and_then(|w| w.hwnd().ok())
        .map(|h| h.0 as *mut std::ffi::c_void);
    #[cfg(not(target_os = "windows"))]
    let hwnd: Option<*mut std::ffi::c_void> = None;

    let config = PlatformConfig {
        dbus_name: "kodama",
        display_name: "Kodama",
        hwnd,
    };

    let mut controls = match MediaControls::new(config) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("[media] failed to create OS media controls: {:?}", e);
            return;
        }
    };

    let app_handle = app.clone();
    let attached = controls.attach(move |event: MediaControlEvent| {
        if let Err(error) = handle_control_event(event, &engine, &audio_tx, &app_handle) {
            eprintln!("[media] control failed: {error}");
        }
    });
    if let Err(e) = attached {
        eprintln!("[media] failed to attach media controls: {:?}", e);
        return;
    }

    CONTROLS.with(|c| *c.borrow_mut() = Some(controls));
}

fn handle_control_event(
    event: MediaControlEvent,
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    app: &AppHandle,
) -> Result<(), String> {
    if matches!(
        event,
        MediaControlEvent::Play
            | MediaControlEvent::Pause
            | MediaControlEvent::Toggle
            | MediaControlEvent::Next
            | MediaControlEvent::Previous
            | MediaControlEvent::Stop
            | MediaControlEvent::SetPosition(_)
            | MediaControlEvent::Seek(_)
            | MediaControlEvent::SeekBy(_, _)
    ) {
        engine.require_local_transport()?;
    }
    match event {
        MediaControlEvent::Play => play(engine, audio_tx, app)?,
        MediaControlEvent::Pause => pause(engine, audio_tx, app)?,
        MediaControlEvent::Toggle => {
            if matches!(
                engine.snapshot()?.status,
                PlaybackStatus::Playing | PlaybackStatus::Loading
            ) {
                pause(engine, audio_tx, app)?;
            } else {
                play(engine, audio_tx, app)?;
            }
        }
        MediaControlEvent::Next => {
            play_selected(engine.select_next()?, "next", audio_tx, app, engine)?;
        }
        MediaControlEvent::Previous => {
            play_selected(engine.select_previous()?, "previous", audio_tx, app, engine)?;
        }
        MediaControlEvent::Stop => {
            let snapshot = engine.update_transport(TransportUpdate {
                status: Some(PlaybackStatus::Stopped),
                position_seconds: Some(0.0),
                ..TransportUpdate::default()
            })?;
            audio_tx
                .send(AudioCmd::Stop)
                .map_err(|error| error.to_string())?;
            emit_snapshot(app, &snapshot);
        }
        MediaControlEvent::SetPosition(MediaPosition(position)) => {
            seek_to(position.as_secs_f64(), engine, audio_tx, app)?;
        }
        MediaControlEvent::Seek(direction) => {
            seek_by(direction, Duration::from_secs(10), engine, audio_tx, app)?;
        }
        MediaControlEvent::SeekBy(direction, amount) => {
            seek_by(direction, amount, engine, audio_tx, app)?;
        }
        _ => {}
    }
    Ok(())
}

fn seek_by(
    direction: SeekDirection,
    amount: Duration,
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    app: &AppHandle,
) -> Result<(), String> {
    let current = engine.snapshot()?.position_seconds;
    let delta = amount.as_secs_f64();
    let requested = match direction {
        SeekDirection::Forward => current + delta,
        SeekDirection::Backward => (current - delta).max(0.0),
    };
    seek_to(requested, engine, audio_tx, app)
}

fn seek_to(
    requested: f64,
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    app: &AppHandle,
) -> Result<(), String> {
    let current = engine.snapshot()?;
    let position_seconds = if current.duration_seconds > 0.0 {
        requested.min(current.duration_seconds)
    } else {
        requested
    };
    let snapshot = engine.update_transport(TransportUpdate {
        position_seconds: Some(position_seconds),
        ..TransportUpdate::default()
    })?;
    audio_tx
        .send(AudioCmd::Seek(position_seconds))
        .map_err(|error| error.to_string())?;
    emit_snapshot(app, &snapshot);
    Ok(())
}

fn play(
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    app: &AppHandle,
) -> Result<(), String> {
    let current = engine.snapshot()?;
    if current.status == PlaybackStatus::Stopped {
        return play_selected(engine.restart_current()?, "play", audio_tx, app, engine);
    }
    audio_tx
        .send(AudioCmd::Resume)
        .map_err(|error| error.to_string())?;
    Ok(())
}

fn pause(
    engine: &PlaybackEngine,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    app: &AppHandle,
) -> Result<(), String> {
    if engine.snapshot()?.status == PlaybackStatus::Stopped {
        return Ok(());
    }
    let snapshot = engine.update_transport(TransportUpdate {
        status: Some(PlaybackStatus::Paused),
        ..TransportUpdate::default()
    })?;
    audio_tx
        .send(AudioCmd::Pause)
        .map_err(|error| error.to_string())?;
    emit_snapshot(app, &snapshot);
    Ok(())
}

fn play_selected(
    request: Option<PlaybackSourceRequest>,
    reason: &str,
    audio_tx: &std::sync::mpsc::SyncSender<AudioCmd>,
    app: &AppHandle,
    engine: &PlaybackEngine,
) -> Result<(), String> {
    let Some(request) = request else {
        return Ok(());
    };
    audio_tx
        .send(AudioCmd::PlayResolved {
            request: request.clone(),
        })
        .map_err(|error| error.to_string())?;
    let _ = app.emit(
        "playback-track-changed",
        serde_json::json!({ "track": request.track, "reason": reason }),
    );
    emit_snapshot(app, &engine.snapshot()?);
    Ok(())
}

fn emit_snapshot(app: &AppHandle, snapshot: &crate::audio::engine::PlaybackSnapshot) {
    let _ = app.emit("playback-state-changed", snapshot);
}

/// Push the current track's metadata + playback state. Main-thread only.
fn apply(
    title: String,
    artist: String,
    album: String,
    cover: String,
    duration: f64,
    playing: bool,
    elapsed: f64,
) {
    CONTROLS.with(|cell| {
        if let Some(controls) = cell.borrow_mut().as_mut() {
            // Only re-push metadata (incl. the cover, the expensive part) when it actually
            // changed — the periodic elapsed-time refresh otherwise janks a frame every 15s.
            let sig = format!("{title}\u{1}{artist}\u{1}{album}\u{1}{cover}\u{1}{duration}");
            let changed = LAST_META.with(|m| {
                let mut m = m.borrow_mut();
                if m.as_deref() == Some(sig.as_str()) {
                    false
                } else {
                    *m = Some(sig);
                    true
                }
            });
            if changed {
                let _ = controls.set_metadata(MediaMetadata {
                    title: Some(&title),
                    artist: Some(&artist),
                    album: if album.is_empty() { None } else { Some(&album) },
                    cover_url: if cover.is_empty() { None } else { Some(&cover) },
                    duration: if duration > 0.0 {
                        Some(Duration::from_secs_f64(duration))
                    } else {
                        None
                    },
                });
            }
            let progress = Some(MediaPosition(Duration::from_secs_f64(elapsed.max(0.0))));
            let _ = controls.set_playback(if playing {
                MediaPlayback::Playing { progress }
            } else {
                MediaPlayback::Paused { progress }
            });
        }
    });
}

fn clear() {
    LAST_META.with(|m| *m.borrow_mut() = None);
    CONTROLS.with(|cell| {
        if let Some(controls) = cell.borrow_mut().as_mut() {
            let _ = controls.set_playback(MediaPlayback::Stopped);
        }
    });
}

pub fn update_from_snapshot(app: &AppHandle, snapshot: &crate::audio::engine::PlaybackSnapshot) {
    let Some(track) = snapshot.current_track.as_ref() else {
        let _ = app.run_on_main_thread(clear);
        return;
    };
    let title = track.title.clone();
    let artist = track.artists.join(", ");
    let album = track.album.clone();
    let thumbnail = track.thumbnail.clone();
    let duration = snapshot.duration_seconds;
    let elapsed = snapshot.position_seconds;
    let playing = snapshot.status == PlaybackStatus::Playing;
    let _ = app.run_on_main_thread(move || {
        apply(title, artist, album, thumbnail, duration, playing, elapsed);
    });
}
