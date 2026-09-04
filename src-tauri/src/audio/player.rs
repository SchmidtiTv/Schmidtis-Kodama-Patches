use rodio::Source;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::Emitter;

use super::analyzer;
use super::decoder::StreamingSource;
use super::engine::{PlaybackEngine, PlaybackStatus, TransportUpdate, MAX_CROSSFADE_SECONDS};
use super::source_loader::{
    build_streaming_source, spawn_automatic_source, spawn_automatic_transition,
    CrossfadeSourceMessage, PcmTransitionMessage, SourceMessage,
};

pub enum AudioCmd {
    Play {
        url: String,
        seek_to: f64,
    },
    PlayResolved {
        request: super::engine::PlaybackSourceRequest,
    },
    Pause,
    Resume,
    Stop,
    Seek(f64),
    SetVolume(f32),
    SetAnalysisEnabled(bool),
}

pub struct AudioPlayer(Mutex<Option<std::sync::mpsc::SyncSender<AudioCmd>>>);

fn crossfade_volumes(volume: f32, progress: f32) -> (f32, f32) {
    let angle = progress.clamp(0.0, 1.0) * std::f32::consts::FRAC_PI_2;
    (volume * angle.cos(), volume * angle.sin())
}

impl AudioPlayer {
    pub fn new() -> Self {
        AudioPlayer(Mutex::new(None))
    }

    pub fn set_sender(&self, sender: std::sync::mpsc::SyncSender<AudioCmd>) {
        *self.0.lock().unwrap() = Some(sender);
    }

    pub fn sender(&self) -> Result<std::sync::mpsc::SyncSender<AudioCmd>, String> {
        self.0
            .lock()
            .map_err(|error| error.to_string())?
            .clone()
            .ok_or_else(|| "Audio player not initialized".to_string())
    }
}

pub fn start_audio_thread(
    app: tauri::AppHandle,
    engine: PlaybackEngine,
) -> std::sync::mpsc::SyncSender<AudioCmd> {
    let (tx, rx) = std::sync::mpsc::sync_channel::<AudioCmd>(64);

    // Shared handle to the analysis buffer of the currently-playing source.
    let current_analysis: Arc<Mutex<Option<Arc<analyzer::AnalysisBuffer>>>> =
        Arc::new(Mutex::new(None));
    let analysis_enabled = Arc::new(AtomicBool::new(false));

    // ── Visualizer analysis thread: snapshot → FFT → bands, emit ~30fps ──
    {
        let app = app.clone();
        let cur = Arc::clone(&current_analysis);
        let enabled = Arc::clone(&analysis_enabled);
        let engine = engine.clone();
        std::thread::spawn(move || {
            let mut az: Option<(u32, analyzer::Analyzer)> = None;
            let mut samples = [0.0f32; analyzer::FFT_SIZE];
            let mut bands = [0.0f32; analyzer::NUM_BANDS];
            let mut last_written = 0usize;
            let mut idle_zeros = 0u32;
            loop {
                std::thread::sleep(std::time::Duration::from_millis(33));
                if !enabled.load(Ordering::Relaxed) || !engine.is_ui_visible() {
                    last_written = 0;
                    continue;
                }
                let buf = { cur.lock().unwrap().clone() };
                let written = buf.as_ref().map(|b| b.written()).unwrap_or(0);
                let active = buf.is_some() && written != last_written;
                last_written = written;
                if active {
                    let buf = buf.unwrap();
                    let sr = buf.sample_rate();
                    if az.as_ref().map(|(s, _)| *s != sr).unwrap_or(true) {
                        az = Some((sr, analyzer::Analyzer::new(sr)));
                    }
                    buf.snapshot(&mut samples);
                    let (raw, level) = az.as_mut().unwrap().1.analyze(&samples);
                    bands.copy_from_slice(&raw); // keep last frame for the decay path
                    idle_zeros = 0;
                    let payload: Vec<f32> =
                        raw.iter().map(|b| (b * 1000.0).round() / 1000.0).collect();
                    let _ = app.emit(
                        "audio-levels",
                        serde_json::json!({ "bands": payload, "level": (level * 1000.0).round() / 1000.0 }),
                    );
                } else {
                    // Paused / nothing playing → decay toward zero, then stop emitting.
                    let mut any = false;
                    for b in bands.iter_mut() {
                        if *b > 0.002 {
                            *b *= 0.82;
                            any = true;
                        } else {
                            *b = 0.0;
                        }
                    }
                    if any || idle_zeros < 2 {
                        if !any {
                            idle_zeros += 1;
                        }
                        let payload: Vec<f32> = bands
                            .iter()
                            .map(|b| (b * 1000.0).round() / 1000.0)
                            .collect();
                        let _ = app.emit(
                            "audio-levels",
                            serde_json::json!({ "bands": payload, "level": 0.0 }),
                        );
                    }
                }
            }
        });
    }
    let current_analysis = Arc::clone(&current_analysis);
    let analysis_enabled_for_player = Arc::clone(&analysis_enabled);

    std::thread::spawn(move || {
        let output = rodio::OutputStream::try_default();
        let (_stream, handle) = match output {
            Ok(pair) => pair,
            Err(e) => {
                eprintln!("[Audio] Output init failed: {e}");
                return;
            }
        };

        let mut sink: Option<rodio::Sink> = None;
        let mut audio_data: Option<Vec<u8>> = None;
        // Resolvable source identity used to rebuild automatic sources on seek.
        let mut source_url: Option<String> = None;
        let mut duration: f64 = 0.0;
        let mut volume: f32 = 0.16f32;
        let mut seek_offset: f64 = 0.0;

        let (data_tx, data_rx) = std::sync::mpsc::channel::<(Vec<u8>, f64, u64)>();
        // Progressive path delivers an already-probed, ready-to-play StreamingSource built off
        // the audio thread (so the probe's network reads don't block command handling).
        let (source_tx, source_rx) = std::sync::mpsc::channel::<SourceMessage>();
        // Buffer fill of the track the UI is showing, reported alongside the play position.
        // `None` for anything not streamed over the network (local files / classic downloads are
        // already complete before they reach a sink), which is the signal for the UI to hide the
        // indicator rather than draw a permanently-full bar.
        let mut dl_progress: Option<super::http_source::DownloadProgress> = None;

        // ── Crossfade: a second sink for the incoming track + an equal-power volume ramp ──
        let mut sink2: Option<rodio::Sink> = None;
        let mut duration2: f64 = 0.0;
        let mut source_url2: Option<String> = None;
        let mut xfade_start: Option<std::time::Instant> = None;
        let mut xfade_dur: f64 = 0.0;
        let (xsource_tx, xsource_rx) = std::sync::mpsc::channel::<CrossfadeSourceMessage>();
        let (pcm_tx, pcm_rx) = std::sync::mpsc::channel::<PcmTransitionMessage>();
        let mut dl_progress2: Option<super::http_source::DownloadProgress> = None;

        let mut play_gen: u64 = 0;

        // The loop below ticks every 20ms for crossfade-ramp accuracy, but neither the engine's
        // transport state (write-locks `PlaybackEngine`'s shared RwLock) nor the `audio-progress`
        // IPC emit (JSON serialize + WebView round-trip) needs that resolution — external readers
        // (UI, the 1Hz integration worker, on-demand snapshot queries) are all fine with ~100ms
        // staleness. Both are throttled together, except a play/pause transition always applies
        // immediately so status changes never lag behind the throttle window.
        const PROGRESS_EMIT_INTERVAL: std::time::Duration = std::time::Duration::from_millis(100);
        let mut last_progress_emit = std::time::Instant::now() - PROGRESS_EMIT_INTERVAL;
        let mut last_transport_status: Option<PlaybackStatus> = None;

        loop {
            while let Ok((data, seek_to, gen)) = data_rx.try_recv() {
                if gen != play_gen {
                    eprintln!("[Audio] Ignoring stale download (gen {gen} != {play_gen})");
                    continue;
                }
                eprintln!("[Audio] Received {} bytes for decoding", data.len());
                if let Some(s) = sink.take() {
                    s.stop();
                }
                duration = 0.0;
                seek_offset = 0.0;
                audio_data = Some(data.clone());

                match StreamingSource::new(data) {
                    Ok(mut source) => {
                        duration = source
                            .total_duration()
                            .map(|d| d.as_secs_f64())
                            .unwrap_or(0.0);
                        eprintln!("[Audio] Streaming started, duration={duration:.1}s");
                        match rodio::Sink::try_new(&handle) {
                            Ok(new_sink) => {
                                new_sink.set_volume(volume);
                                *current_analysis.lock().unwrap() = Some(
                                    source
                                        .enable_analysis(Arc::clone(&analysis_enabled_for_player)),
                                );
                                new_sink.append(source);
                                if seek_to > 0.05 {
                                    let _ = new_sink
                                        .try_seek(std::time::Duration::from_secs_f64(seek_to));
                                }
                                let start_paused = engine
                                    .snapshot()
                                    .map(|snapshot| snapshot.status == PlaybackStatus::Paused)
                                    .unwrap_or(false);
                                if start_paused {
                                    new_sink.pause();
                                }
                                let _ = app.emit(
                                    "audio-loaded",
                                    serde_json::json!({ "duration": duration }),
                                );
                                sink = Some(new_sink);
                                let _ = engine.update_runtime_transport(
                                    if start_paused {
                                        PlaybackStatus::Paused
                                    } else {
                                        PlaybackStatus::Playing
                                    },
                                    seek_to,
                                    duration,
                                );
                            }
                            Err(e) => eprintln!("[Audio] Sink error: {e}"),
                        }
                    }
                    Err(e) => {
                        eprintln!("[Audio] Decode error: {e}");
                        let _ = app.emit("audio-error", format!("{e}"));
                    }
                }
            }

            // Progressive (HTTP-streamed) sources, already probed off-thread.
            while let Ok((mut source, gen, start_paused, loaded_url, progress)) =
                source_rx.try_recv()
            {
                if gen != play_gen {
                    eprintln!("[Audio] Ignoring stale stream source (gen {gen} != {play_gen})");
                    continue;
                }
                dl_progress = progress;
                if let Some(s) = sink.take() {
                    s.stop();
                }
                // seek_offset was set by the Play/Seek handler (the source decodes from there).
                duration = source
                    .total_duration()
                    .map(|d| d.as_secs_f64())
                    .unwrap_or(0.0);
                source_url = Some(loaded_url);
                let start_paused = start_paused
                    || engine
                        .snapshot()
                        .map(|snapshot| snapshot.status == PlaybackStatus::Paused)
                        .unwrap_or(false);
                match rodio::Sink::try_new(&handle) {
                    Ok(new_sink) => {
                        new_sink.set_volume(volume);
                        *current_analysis.lock().unwrap() =
                            Some(source.enable_analysis(Arc::clone(&analysis_enabled_for_player)));
                        new_sink.append(source);
                        if start_paused {
                            new_sink.pause();
                        }
                        let _ =
                            app.emit("audio-loaded", serde_json::json!({ "duration": duration }));
                        sink = Some(new_sink);
                        let _ = engine.update_runtime_transport(
                            if start_paused {
                                PlaybackStatus::Paused
                            } else {
                                PlaybackStatus::Playing
                            },
                            seek_offset,
                            duration,
                        );
                        eprintln!("[Audio] Progressive stream playing, duration={duration:.1}s");
                    }
                    Err(e) => eprintln!("[Audio] Sink error: {e}"),
                }
            }

            // A prepared Mix transition replaces the current tail with one rendered PCM source,
            // followed by the buffered incoming continuation on that same sink.
            while let Ok(message) = pcm_rx.try_recv() {
                if message.generation != play_gen || sink.is_none() {
                    continue;
                }
                let start_paused = sink.as_ref().is_some_and(|current| current.is_paused());
                let new_sink = match rodio::Sink::try_new(&handle) {
                    Ok(sink) => sink,
                    Err(error) => {
                        let _ = engine.fail_crossfade();
                        let _ = app.emit("audio-crossfade-failed", ());
                        eprintln!("[Audio] PCM transition sink error: {error}");
                        continue;
                    }
                };
                let committed_track = match engine.commit_crossfade(if start_paused {
                    PlaybackStatus::Paused
                } else {
                    PlaybackStatus::Playing
                }) {
                    Ok(Some(track)) => track,
                    _ => {
                        new_sink.stop();
                        continue;
                    }
                };
                let mix_seconds = message.pcm.len() as f64
                    / (f64::from(message.channels) * f64::from(message.sample_rate));
                new_sink.set_volume(volume);
                new_sink.append(rodio::buffer::SamplesBuffer::new(
                    message.channels,
                    message.sample_rate,
                    message.pcm,
                ));
                let mut continuation = message.continuation;
                *current_analysis.lock().unwrap() =
                    Some(continuation.enable_analysis(Arc::clone(&analysis_enabled_for_player)));
                new_sink.append(continuation);
                if start_paused {
                    new_sink.pause();
                }
                if let Some(old_sink) = sink.replace(new_sink) {
                    old_sink.stop();
                }
                duration = message.duration;
                // Map the combined source clock onto incoming-track time once the PCM prefix ends.
                seek_offset = message.incoming_offset_seconds - mix_seconds;
                audio_data = None;
                source_url = Some(message.url);
                dl_progress = message.continuation_progress;
                let _ = app.emit("audio-loaded", serde_json::json!({ "duration": duration }));
                let _ = app.emit("audio-crossfade-started", ());
                let _ = app.emit(
                    "playback-track-changed",
                    serde_json::json!({ "track": committed_track, "reason": "crossfade" }),
                );
                eprintln!("[Audio] Single-sink PCM Mix transition started");
            }

            // Incoming fallback source: start it on sink2 at volume 0 and begin the ramp.
            while let Ok((mut source, url, dur, gen, automatic, progress)) = xsource_rx.try_recv() {
                if gen != play_gen {
                    // A seek or track change superseded this build. Its engine request was
                    // already cancelled with the generation change, so it is not a failure.
                    continue;
                }
                if sink.is_none() {
                    // The outgoing track ended while the source was being built — abort so the
                    // regular end-of-track path can load the next item normally.
                    if automatic {
                        let _ = engine.fail_crossfade();
                    }
                    let _ = app.emit("audio-crossfade-failed", ());
                    continue;
                }
                if let Some(s) = sink2.take() {
                    s.stop();
                }
                duration2 = source
                    .total_duration()
                    .map(|d| d.as_secs_f64())
                    .unwrap_or(0.0);
                source_url2 = Some(url);
                dl_progress2 = progress;
                match rodio::Sink::try_new(&handle) {
                    Ok(s2) => {
                        let start_paused = sink.as_ref().is_some_and(|current| current.is_paused());
                        let committed_track = if automatic {
                            match engine.commit_crossfade(if start_paused {
                                PlaybackStatus::Paused
                            } else {
                                PlaybackStatus::Playing
                            }) {
                                Ok(Some(track)) => Some(track),
                                _ => {
                                    s2.stop();
                                    continue;
                                }
                            }
                        } else {
                            None
                        };
                        s2.set_volume(0.0);
                        // The visualizer follows the incoming track (the UI already shows it).
                        *current_analysis.lock().unwrap() =
                            Some(source.enable_analysis(Arc::clone(&analysis_enabled_for_player)));
                        s2.append(source);
                        if start_paused {
                            s2.pause();
                        }
                        sink2 = Some(s2);
                        xfade_start = Some(std::time::Instant::now());
                        xfade_dur = dur.max(0.1);
                        let _ =
                            app.emit("audio-loaded", serde_json::json!({ "duration": duration2 }));
                        let _ = app.emit("audio-crossfade-started", ());
                        if let Some(track) = committed_track {
                            let _ = app.emit(
                                "playback-track-changed",
                                serde_json::json!({ "track": track, "reason": "crossfade" }),
                            );
                        }
                        eprintln!("[Audio] Crossfade started over {xfade_dur:.1}s, next duration={duration2:.1}s");
                    }
                    Err(e) => {
                        if automatic {
                            let _ = engine.fail_crossfade();
                        }
                        let _ = app.emit("audio-crossfade-failed", ());
                        eprintln!("[Audio] Crossfade sink error: {e}");
                    }
                }
            }

            while let Ok(cmd) = rx.try_recv() {
                match cmd {
                    AudioCmd::Play { url, seek_to } => {
                        let _ = engine.cancel_crossfade();
                        let _ = engine.update_transport(TransportUpdate {
                            status: Some(PlaybackStatus::Loading),
                            position_seconds: Some(seek_to),
                            duration_seconds: Some(0.0),
                            ..TransportUpdate::default()
                        });
                        if let Some(s) = sink.take() {
                            s.stop();
                        }
                        if let Some(s) = sink2.take() {
                            s.stop();
                        }
                        xfade_start = None;
                        source_url2 = None;
                        dl_progress2 = None;
                        duration = 0.0;
                        seek_offset = 0.0;
                        audio_data = None;
                        source_url = None;
                        dl_progress = None;
                        play_gen += 1;
                        let gen = play_gen;

                        // Progressive: the /audio-stream proxy streams with byte-range support →
                        // build the streaming source off-thread and play as soon as it's probed.
                        if url.contains("/audio-stream/") {
                            source_url = Some(url.clone());
                            seek_offset = seek_to; // source decodes from seek_to; report offset
                            let stx = source_tx.clone();
                            let dl_app = app.clone();
                            std::thread::spawn(move || {
                                eprintln!("[Audio] Progressive stream (gen {gen})");
                                let source_url = url.clone();
                                let built = super::http_source::HttpStream::new(url)
                                    .map_err(|e| e.to_string())
                                    .and_then(|hs| {
                                        // Take the progress handle before the box hands the
                                        // stream over — afterwards it is out of reach.
                                        let progress = hs.progress();
                                        super::decoder::StreamingSource::new_streaming(
                                            Box::new(hs),
                                            seek_to,
                                        )
                                        .map(|s| (s, progress))
                                    });
                                match built {
                                    Ok((source, progress)) => {
                                        let _ = stx.send((
                                            source,
                                            gen,
                                            false,
                                            source_url,
                                            Some(progress),
                                        ));
                                    }
                                    Err(e) => {
                                        eprintln!(
                                            "[Audio] Progressive load error (gen {gen}): {e}"
                                        );
                                        let _ = dl_app
                                            .emit("audio-error", format!("Stream failed: {e}"));
                                    }
                                }
                            });
                            continue;
                        }

                        let dtx = data_tx.clone();
                        let dl_app = app.clone();

                        std::thread::spawn(move || {
                            let result = if url.starts_with("file://") {
                                let path = url.strip_prefix("file://").unwrap();
                                let path = path.replace("%20", " ");
                                eprintln!("[Audio] Reading from disk (gen {gen}): {path}");
                                std::fs::read(&path).map_err(|e| format!("File read error: {e}"))
                            } else {
                                eprintln!(
                                    "[Audio] HTTP download (gen {gen}): {}…",
                                    &url[..url.len().min(80)]
                                );
                                (|| -> Result<Vec<u8>, String> {
                                    let client = reqwest::blocking::Client::builder()
                                        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                                        .timeout(std::time::Duration::from_secs(120))
                                        .build()
                                        .map_err(|e| e.to_string())?;
                                    let resp =
                                        client.get(&url).send().map_err(|e| e.to_string())?;
                                    if !resp.status().is_success() {
                                        return Err(format!("HTTP {}", resp.status()));
                                    }
                                    resp.bytes().map(|b| b.to_vec()).map_err(|e| e.to_string())
                                })()
                            };
                            match result {
                                Ok(data) => {
                                    eprintln!("[Audio] Loaded {} bytes (gen {gen})", data.len());
                                    let _ = dtx.send((data, seek_to, gen));
                                }
                                Err(e) => {
                                    eprintln!("[Audio] Load error (gen {gen}): {e}");
                                    let _ = dl_app.emit("audio-error", format!("Load failed: {e}"));
                                }
                            }
                        });
                    }
                    AudioCmd::PlayResolved { request } => {
                        let _ = engine.cancel_crossfade();
                        if let Some(s) = sink.take() {
                            s.stop();
                        }
                        if let Some(s) = sink2.take() {
                            s.stop();
                        }
                        xfade_start = None;
                        source_url2 = None;
                        dl_progress2 = None;
                        duration = 0.0;
                        seek_offset = 0.0;
                        audio_data = None;
                        source_url = None;
                        dl_progress = None;
                        play_gen = play_gen.wrapping_add(1);
                        spawn_automatic_source(
                            request,
                            play_gen,
                            source_tx.clone(),
                            app.clone(),
                            engine.clone(),
                        );
                    }
                    AudioCmd::Pause => {
                        if let Some(s) = &sink {
                            s.pause();
                        }
                        if let Some(s) = &sink2 {
                            s.pause();
                        }
                        let _ = engine.update_transport(TransportUpdate {
                            status: Some(PlaybackStatus::Paused),
                            ..TransportUpdate::default()
                        });
                    }
                    AudioCmd::Resume => {
                        if sink.is_some() || sink2.is_some() {
                            if let Some(s) = &sink {
                                s.play();
                            }
                            if let Some(s) = &sink2 {
                                s.play();
                            }
                            let _ = engine.update_transport(TransportUpdate {
                                status: Some(PlaybackStatus::Playing),
                                ..TransportUpdate::default()
                            });
                        } else if let Ok(Some(request)) = engine.restart_current() {
                            play_gen = play_gen.wrapping_add(1);
                            let track = request.track.clone();
                            spawn_automatic_source(
                                request,
                                play_gen,
                                source_tx.clone(),
                                app.clone(),
                                engine.clone(),
                            );
                            let _ = app.emit(
                                "playback-track-changed",
                                serde_json::json!({ "track": track, "reason": "resumeRestart" }),
                            );
                        }
                        if let Ok(snapshot) = engine.snapshot() {
                            let _ = app.emit("playback-state-changed", snapshot);
                        }
                    }
                    AudioCmd::Stop => {
                        let _ = engine.cancel_crossfade();
                        if let Some(s) = sink.take() {
                            s.stop();
                        }
                        if let Some(s) = sink2.take() {
                            s.stop();
                        }
                        xfade_start = None;
                        source_url2 = None;
                        dl_progress2 = None;
                        duration = 0.0;
                        audio_data = None;
                        source_url = None;
                        dl_progress = None;
                        let _ = engine.update_transport(TransportUpdate {
                            status: Some(PlaybackStatus::Stopped),
                            position_seconds: Some(0.0),
                            duration_seconds: Some(0.0),
                            ..TransportUpdate::default()
                        });
                    }
                    AudioCmd::Seek(t) => {
                        // A seek changes the outgoing track's fade window. Discard any source
                        // that was still being built for its previous position before rebuilding
                        // the primary source below.
                        let _ = engine.cancel_crossfade();
                        // Do not invalidate an initial source that is still loading: there is no
                        // active sink (and therefore no fade) to replace yet.
                        if sink.is_some() {
                            play_gen = play_gen.wrapping_add(1);
                        }
                        // The engine commits the incoming track when a crossfade starts. Promote
                        // that matching sink before seeking so the old source cannot replace it.
                        if xfade_start.is_some() {
                            if let Some(s) = sink.take() {
                                s.stop();
                            }
                            sink = sink2.take();
                            if let Some(s) = &sink {
                                s.set_volume(volume);
                            }
                            duration = duration2;
                            seek_offset = 0.0;
                            audio_data = None;
                            source_url = source_url2.take();
                            dl_progress = dl_progress2.take();
                            xfade_start = None;
                            let _ = app.emit("audio-crossfade-done", ());
                        }
                        let _ = engine.update_transport(TransportUpdate {
                            position_seconds: Some(t),
                            ..TransportUpdate::default()
                        });
                        let was_paused = sink.as_ref().map(|s| s.is_paused()).unwrap_or(false);
                        if let Some(url) = source_url.clone() {
                            if let Some(s) = sink.take() {
                                s.stop();
                            }
                            seek_offset = t;
                            let gen = play_gen;
                            let stx = source_tx.clone();
                            // Seeking rebuilds the decoder, but it must not restart the download:
                            // read the already-buffered bytes through a second reader over the
                            // same stream. A backwards seek then costs nothing, and the buffer
                            // indicator keeps what it had reached instead of dropping to zero.
                            let existing = dl_progress.clone();
                            std::thread::spawn(move || {
                                let source_url = url.clone();
                                let built = build_streaming_source(&url, t, existing);
                                if let Ok((source, progress)) = built {
                                    let _ =
                                        stx.send((source, gen, was_paused, source_url, progress));
                                }
                            });
                        } else if let Some(ref data) = audio_data {
                            if let Some(s) = sink.take() {
                                s.stop();
                            }
                            if let Ok(mut source) = StreamingSource::new_with_seek(data.clone(), t)
                            {
                                seek_offset = t;
                                if let Ok(new_sink) = rodio::Sink::try_new(&handle) {
                                    new_sink.set_volume(volume);
                                    *current_analysis.lock().unwrap() =
                                        Some(source.enable_analysis(Arc::clone(
                                            &analysis_enabled_for_player,
                                        )));
                                    new_sink.append(source);
                                    if was_paused {
                                        new_sink.pause();
                                    }
                                    sink = Some(new_sink);
                                    eprintln!("[Audio] Seeked to {t:.1}s");
                                }
                            }
                        }
                    }
                    AudioCmd::SetVolume(v) => {
                        volume = v;
                        // During a crossfade the two sinks are mid-ramp; rescale both to keep
                        // their relative fade. Otherwise just set the single sink.
                        if let Some(start) = xfade_start {
                            let p =
                                (start.elapsed().as_secs_f64() / xfade_dur).clamp(0.0, 1.0) as f32;
                            let (outgoing, incoming) = crossfade_volumes(v, p);
                            if let Some(s) = &sink {
                                s.set_volume(outgoing);
                            }
                            if let Some(s) = &sink2 {
                                s.set_volume(incoming);
                            }
                        } else if let Some(s) = &sink {
                            s.set_volume(v);
                        }
                    }
                    AudioCmd::SetAnalysisEnabled(enabled) => {
                        analysis_enabled_for_player.store(enabled, Ordering::Relaxed);
                    }
                }
            }

            // The native engine owns the crossfade decision. It chooses the next queued track,
            // applies per-transition overrides, and marks the request pending before any I/O
            // starts, preventing duplicate builds while the WebView is hidden or throttled.
            if xfade_start.is_none() && sink2.is_none() {
                if let Some(current_sink) = sink.as_ref().filter(|sink| !sink.is_paused()) {
                    let position = current_sink.get_pos().as_secs_f64() + seek_offset;
                    // Cheap arithmetic gate before even asking the engine: a crossfade can only
                    // become due once fewer than MAX_CROSSFADE_SECONDS remain, so this skips the
                    // engine call entirely (no lock, no queue lookup) for the rest of every track.
                    let maybe_due = duration > 0.0 && duration - position <= MAX_CROSSFADE_SECONDS;
                    if maybe_due {
                        if let Ok(Some(request)) = engine.prepare_crossfade(position, duration) {
                            spawn_automatic_transition(
                                request,
                                source_url.clone(),
                                position,
                                play_gen,
                                pcm_tx.clone(),
                                xsource_tx.clone(),
                                app.clone(),
                                engine.clone(),
                            );
                        }
                    }
                }
            }

            // ── Crossfade ramp + promotion ──
            if let Some(start) = xfade_start {
                let p = (start.elapsed().as_secs_f64() / xfade_dur).clamp(0.0, 1.0) as f32;
                let (outgoing, incoming) = crossfade_volumes(volume, p);
                if let Some(s) = &sink {
                    s.set_volume(outgoing);
                }
                if let Some(s) = &sink2 {
                    s.set_volume(incoming);
                }
                // Done when the ramp completes or the outgoing track runs out.
                let out_ended = sink.as_ref().map(|s| s.empty()).unwrap_or(true);
                if p >= 1.0 || out_ended {
                    if let Some(s) = sink.take() {
                        s.stop();
                    }
                    sink = sink2.take();
                    if let Some(s) = &sink {
                        s.set_volume(volume);
                    }
                    duration = duration2;
                    seek_offset = 0.0;
                    audio_data = None;
                    source_url = source_url2.take();
                    dl_progress = dl_progress2.take();
                    xfade_start = None;
                    let _ = app.emit("audio-crossfade-done", ());
                    eprintln!("[Audio] Crossfade promoted incoming track");
                }
            }

            // Report progress for whatever the UI is showing: during a crossfade that's the
            // incoming track (sink2); otherwise the primary sink.
            if let Some(s) = sink2.as_ref().filter(|_| xfade_start.is_some()) {
                let position = s.get_pos().as_secs_f64();
                let paused = s.is_paused();
                let status = if paused {
                    PlaybackStatus::Paused
                } else {
                    PlaybackStatus::Playing
                };
                let due = last_transport_status != Some(status)
                    || last_progress_emit.elapsed() >= PROGRESS_EMIT_INTERVAL;
                if due {
                    let _ = engine.update_runtime_transport(status, position, duration2);
                    last_transport_status = Some(status);
                    if engine.is_ui_visible() {
                        last_progress_emit = std::time::Instant::now();
                        // `buffered` stays null unless this really is a network stream, so the UI
                        // can hide the indicator rather than draw a permanently-full bar for local
                        // files and classic downloads.
                        let _ = app.emit(
                            "audio-progress",
                            serde_json::json!({ "position": position, "duration": duration2, "paused": paused, "buffered": dl_progress2.as_ref().and_then(|p| p.fraction()) }),
                        );
                    }
                }
            } else if let Some(s) = &sink {
                let pos = s.get_pos().as_secs_f64() + seek_offset;
                let paused = s.is_paused();
                let ended = s.empty();
                let status = if paused {
                    PlaybackStatus::Paused
                } else {
                    PlaybackStatus::Playing
                };
                let due = last_transport_status != Some(status)
                    || last_progress_emit.elapsed() >= PROGRESS_EMIT_INTERVAL;
                if due {
                    let _ = engine.update_runtime_transport(status, pos, duration);
                    last_transport_status = Some(status);
                    if engine.is_ui_visible() {
                        last_progress_emit = std::time::Instant::now();
                        let _ = app.emit(
                            "audio-progress",
                            serde_json::json!({ "position": pos, "duration": duration, "paused": paused, "buffered": dl_progress.as_ref().and_then(|p| p.fraction()) }),
                        );
                    }
                }
                if ended {
                    sink = None;
                    duration = 0.0;
                    seek_offset = 0.0;
                    audio_data = None;
                    source_url = None;
                    dl_progress = None;
                    play_gen = play_gen.wrapping_add(1);
                    match engine.advance_after_end() {
                        Ok(Some(request)) => {
                            let _ = app.emit(
                                "playback-track-changed",
                                serde_json::json!({
                                    "track": request.track.clone(),
                                    "reason": "naturalEnd"
                                }),
                            );
                            spawn_automatic_source(
                                request,
                                play_gen,
                                source_tx.clone(),
                                app.clone(),
                                engine.clone(),
                            );
                        }
                        Ok(None) => {
                            if let Ok(snapshot) = engine.snapshot() {
                                let _ = app.emit("playback-state-changed", snapshot);
                            }
                            let _ = app.emit("audio-ended", ());
                        }
                        Err(error) => {
                            let _ = app.emit("audio-error", error);
                        }
                    }
                }
            }

            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    });

    tx
}

pub fn send_audio(state: &tauri::State<AudioPlayer>, cmd: AudioCmd) -> Result<(), String> {
    state.sender()?.send(cmd).map_err(|e| e.to_string())
}

/// The equaliser curve. Stored globally rather than handed to each source: playback creates
/// sources in eight different places, and two of them exist at once during a crossfade.
/// Sources pick the change up on their next sample, so moving a slider is audible immediately
/// without restarting anything.
#[tauri::command]
pub fn audio_set_eq(enabled: bool, preamp_db: f32, gains_db: Vec<f32>) -> Result<(), String> {
    if gains_db.len() != super::eq::BANDS {
        return Err(format!("expected {} bands, got {}", super::eq::BANDS, gains_db.len()));
    }
    let mut gains = [0.0f32; super::eq::BANDS];
    for (slot, g) in gains.iter_mut().zip(gains_db) {
        // The UI clamps too, but this is a public command surface and a wild value here would
        // reach the filter design straight away.
        *slot = if g.is_finite() { g.clamp(-24.0, 24.0) } else { 0.0 };
    }
    super::eq::set_config(super::eq::EqConfig {
        enabled,
        preamp_db: if preamp_db.is_finite() { preamp_db.clamp(-24.0, 24.0) } else { 0.0 },
        gains_db: gains,
    });
    Ok(())
}

#[tauri::command]
pub fn audio_play(
    state: tauri::State<AudioPlayer>,
    url: String,
    seek_to: f64,
) -> Result<(), String> {
    let is_local = url.starts_with("file://") || {
        let p = std::path::Path::new(&url);
        p.is_absolute() && url.contains("kiyoshi-audio")
    };
    let is_local_http =
        url.starts_with("http://localhost:") || url.starts_with("http://127.0.0.1:");
    if !is_local && !is_local_http {
        return Err("audio_play: rejected non-local URL".into());
    }
    send_audio(&state, AudioCmd::Play { url, seek_to })
}

#[tauri::command]
pub fn audio_pause(state: tauri::State<AudioPlayer>) -> Result<(), String> {
    send_audio(&state, AudioCmd::Pause)
}

#[tauri::command]
pub fn audio_resume(state: tauri::State<AudioPlayer>) -> Result<(), String> {
    send_audio(&state, AudioCmd::Resume)
}

#[tauri::command]
pub fn audio_stop(state: tauri::State<AudioPlayer>) -> Result<(), String> {
    send_audio(&state, AudioCmd::Stop)
}

#[tauri::command]
pub fn audio_seek(state: tauri::State<AudioPlayer>, position: f64) -> Result<(), String> {
    send_audio(&state, AudioCmd::Seek(position))
}

#[tauri::command]
pub fn audio_set_volume(state: tauri::State<AudioPlayer>, volume: f32) -> Result<(), String> {
    send_audio(&state, AudioCmd::SetVolume(volume))
}

#[tauri::command]
pub fn audio_set_analysis_enabled(
    state: tauri::State<AudioPlayer>,
    enabled: bool,
) -> Result<(), String> {
    send_audio(&state, AudioCmd::SetAnalysisEnabled(enabled))
}
