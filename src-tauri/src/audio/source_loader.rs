use rodio::Source;
use tauri::Emitter;

use super::decoder::StreamingSource;
use super::engine::{
    CrossfadeRequest, PlaybackEngine, PlaybackSourceRequest, PlaybackStatus, TransportUpdate,
};
use super::http_source::DownloadProgress;
use super::mix_processor::render_transition;

pub(super) type SourceMessage = (StreamingSource, u64, bool, String, Option<DownloadProgress>);
pub(super) type CrossfadeSourceMessage =
    (StreamingSource, String, f64, u64, bool, Option<DownloadProgress>);

pub(super) struct PcmTransitionMessage {
    pub pcm: Vec<f32>,
    pub channels: u16,
    pub sample_rate: u32,
    pub continuation: StreamingSource,
    pub continuation_progress: Option<DownloadProgress>,
    pub url: String,
    pub duration: f64,
    pub incoming_offset_seconds: f64,
    pub generation: u64,
}

/// Builds a ready-to-play source for any of our URL kinds. Only the network-streamed case
/// returns a progress handle — the other two branches have the whole file in hand before they
/// return, so there is nothing to watch and the caller reports them as fully buffered.
pub(super) fn build_streaming_source(
    url: &str,
    seek_to: f64,
) -> Result<(StreamingSource, Option<DownloadProgress>), String> {
    if url.contains("/audio-stream/") {
        let source = super::http_source::HttpStream::new(url.to_string())
            .map_err(|error| error.to_string())?;
        let progress = source.progress();
        return StreamingSource::new_streaming(Box::new(source), seek_to)
            .map(|s| (s, Some(progress)));
    }
    if let Some(path) = url.strip_prefix("file://") {
        let data = std::fs::read(path.replace("%20", " "))
            .map_err(|error| format!("File read error: {error}"))?;
        return StreamingSource::new_with_seek(data, seek_to).map(|s| (s, None));
    }

    let client = reqwest::blocking::Client::builder()
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .map_err(|error| error.to_string())?;
    let response = client.get(url).send().map_err(|error| error.to_string())?;
    if !response.status().is_success() {
        return Err(format!("HTTP {}", response.status()));
    }
    let data = response
        .bytes()
        .map(|bytes| bytes.to_vec())
        .map_err(|error| error.to_string())?;
    StreamingSource::new_with_seek(data, seek_to).map(|s| (s, None))
}

fn resolve_automatic_source(request: &PlaybackSourceRequest) -> Result<String, String> {
    let cached_url = format!(
        "http://localhost:9847/song/cached/{}",
        request.track.video_id
    );
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .map_err(|error| error.to_string())?;
    if client
        .head(&cached_url)
        .send()
        .map(|response| response.status().is_success())
        .unwrap_or(false)
    {
        return Ok(cached_url);
    }
    if request.progressive {
        return Ok(format!(
            "http://localhost:9847/audio-stream/{}",
            request.track.video_id
        ));
    }

    let response = client
        .get(format!(
            "http://localhost:9847/stream-prepare/{}",
            request.track.video_id
        ))
        .send()
        .map_err(|error| error.to_string())?;
    if !response.status().is_success() {
        return Err(format!(
            "stream prepare returned HTTP {}",
            response.status()
        ));
    }
    let payload: serde_json::Value = response.json().map_err(|error| error.to_string())?;
    let path = payload
        .get("path")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| {
            payload
                .get("error")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("stream prepare did not return a path")
                .to_string()
        })?;
    Ok(format!("file://{}", path.replace('\\', "/")))
}

pub(super) fn spawn_automatic_source(
    request: PlaybackSourceRequest,
    generation: u64,
    source_tx: std::sync::mpsc::Sender<SourceMessage>,
    app: tauri::AppHandle,
    engine: PlaybackEngine,
) {
    std::thread::spawn(move || {
        let result = resolve_automatic_source(&request).and_then(|url| {
            build_streaming_source(&url, 0.0).map(|(source, progress)| (source, url, progress))
        });
        match result {
            Ok((source, url, progress)) => {
                let _ = source_tx.send((source, generation, false, url, progress));
            }
            Err(error) => {
                let _ = engine.update_transport(TransportUpdate {
                    status: Some(PlaybackStatus::Stopped),
                    ..TransportUpdate::default()
                });
                if let Ok(snapshot) = engine.snapshot() {
                    let _ = app.emit("playback-state-changed", snapshot);
                }
                let _ = app.emit(
                    "audio-error",
                    format!(
                        "Could not load queued track {}: {error}",
                        request.track.video_id
                    ),
                );
            }
        }
    });
}

pub(super) fn spawn_automatic_crossfade(
    request: CrossfadeRequest,
    generation: u64,
    source_tx: std::sync::mpsc::Sender<CrossfadeSourceMessage>,
    app: tauri::AppHandle,
    engine: PlaybackEngine,
) {
    std::thread::spawn(move || {
        let source_request = PlaybackSourceRequest {
            track: request.to_track.clone(),
            progressive: request.progressive,
        };
        let result = resolve_automatic_source(&source_request).and_then(|url| {
            build_streaming_source(&url, 0.0).map(|(source, progress)| (source, url, progress))
        });
        match result {
            Ok((source, url, progress)) => {
                let _ = source_tx.send((source, url, request.seconds, generation, true, progress));
            }
            Err(error) => {
                let _ = engine.fail_crossfade();
                eprintln!(
                    "[Audio] Automatic crossfade build failed for {}: {error}",
                    request.to_track.video_id
                );
                let _ = app.emit("audio-crossfade-failed", ());
            }
        }
    });
}

/// Builds a bounded, single-sink PCM handoff when a Mix pair is available. Every preparation
/// error deliberately falls through to the existing two-sink crossfade sender.
pub(super) fn spawn_automatic_transition(
    request: CrossfadeRequest,
    outgoing_url: Option<String>,
    outgoing_position: f64,
    generation: u64,
    pcm_tx: std::sync::mpsc::Sender<PcmTransitionMessage>,
    crossfade_tx: std::sync::mpsc::Sender<CrossfadeSourceMessage>,
    app: tauri::AppHandle,
    engine: PlaybackEngine,
) {
    let Some(transition) = request.mix_transition.clone() else {
        spawn_automatic_crossfade(request, generation, crossfade_tx, app, engine);
        return;
    };
    let Some(outgoing_url) = outgoing_url else {
        spawn_automatic_crossfade(request, generation, crossfade_tx, app, engine);
        return;
    };
    std::thread::spawn(move || {
        let fallback_request = request.clone();
        let rendered = (|| -> Result<PcmTransitionMessage, String> {
            let source_request = PlaybackSourceRequest {
                track: request.to_track.clone(),
                progressive: request.progressive,
            };
            let incoming_url = resolve_automatic_source(&source_request)?;
            let (mut outgoing, _) = build_streaming_source(&outgoing_url, outgoing_position)?;
            let (mut incoming, _) = build_streaming_source(&incoming_url, 0.0)?;
            if outgoing.channels() != incoming.channels()
                || outgoing.sample_rate() != incoming.sample_rate()
            {
                return Err("PCM transition source formats do not match".to_string());
            }
            let channels = incoming.channels();
            let sample_rate = incoming.sample_rate();
            let frames = (request.seconds * sample_rate as f64).ceil() as usize;
            // Allow the stretcher's fastest supported ratio plus a beat-leading window.
            let incoming_frames = ((frames as f32 * 1.5).ceil() as usize)
                .saturating_add((sample_rate as f64 * 0.1) as usize);
            let outgoing_pcm = collect_frames(&mut outgoing, frames, channels);
            let incoming_pcm = collect_frames(&mut incoming, incoming_frames, channels);
            let rendered = render_transition(
                &outgoing_pcm,
                &incoming_pcm,
                channels,
                sample_rate,
                request.seconds,
                &transition,
                request.mix_tempo_lock,
            )?;
            let (continuation, continuation_progress) =
                build_streaming_source(&incoming_url, rendered.incoming_offset_seconds)?;
            let duration = continuation
                .total_duration()
                .map(|value| value.as_secs_f64())
                .unwrap_or(0.0);
            Ok(PcmTransitionMessage {
                pcm: rendered.pcm,
                channels,
                sample_rate,
                continuation,
                continuation_progress,
                url: incoming_url,
                duration,
                incoming_offset_seconds: rendered.incoming_offset_seconds,
                generation,
            })
        })();
        match rendered {
            Ok(message) => {
                let _ = pcm_tx.send(message);
            }
            Err(error) => {
                eprintln!("[Audio] PCM Mix transition unavailable; using sink crossfade: {error}");
                spawn_automatic_crossfade(fallback_request, generation, crossfade_tx, app, engine);
            }
        }
    });
}

fn collect_frames(source: &mut StreamingSource, frames: usize, channels: u16) -> Vec<f32> {
    let samples = frames.saturating_mul(usize::from(channels));
    source.by_ref().take(samples).collect()
}
