use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock, RwLockReadGuard, RwLockWriteGuard};

use super::model::{
    CrossfadeRequest, MixTransition, PlaybackIntegrationSettings, PlaybackSnapshot, PlaybackStatus,
    PlaybackTrack, TransportUpdate,
};

pub(super) const MAX_QUEUE_TRACKS: usize = 10_000;

#[derive(Clone, Debug)]
pub(super) struct TransitionPolicy {
    pub crossfade_seconds: f64,
    pub crossfade_overrides: HashMap<(String, String), f64>,
    pub progressive: bool,
    pub automatic_crossfade: bool,
    pub mix_transitions: HashMap<(String, String), MixTransition>,
    pub mix_enabled: bool,
    pub mix_tempo_lock: bool,
}

impl Default for TransitionPolicy {
    fn default() -> Self {
        Self {
            crossfade_seconds: 0.0,
            crossfade_overrides: HashMap::new(),
            progressive: true,
            automatic_crossfade: true,
            mix_transitions: HashMap::new(),
            mix_enabled: true,
            mix_tempo_lock: true,
        }
    }
}

#[derive(Clone, Debug)]
pub(super) struct EngineState {
    pub snapshot: PlaybackSnapshot,
    pub policy: TransitionPolicy,
    pub pending_crossfade: Option<CrossfadeRequest>,
    pub failed_crossfade_from: Option<String>,
    pub integrations: PlaybackIntegrationSettings,
    pub current_track_liked: bool,
}

impl Default for EngineState {
    fn default() -> Self {
        Self {
            snapshot: PlaybackSnapshot::default(),
            policy: TransitionPolicy::default(),
            pending_crossfade: None,
            failed_crossfade_from: None,
            integrations: PlaybackIntegrationSettings::default(),
            current_track_liked: false,
        }
    }
}

#[derive(Clone)]
pub struct PlaybackEngine {
    state: Arc<RwLock<EngineState>>,
    ui_visible: Arc<AtomicBool>,
}

impl Default for PlaybackEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl PlaybackEngine {
    pub fn new() -> Self {
        Self {
            state: Arc::new(RwLock::new(EngineState::default())),
            ui_visible: Arc::new(AtomicBool::new(true)),
        }
    }

    pub fn set_ui_visible(&self, visible: bool) {
        self.ui_visible.store(visible, Ordering::Relaxed);
    }

    pub fn is_ui_visible(&self) -> bool {
        self.ui_visible.load(Ordering::Relaxed)
    }

    pub fn snapshot(&self) -> Result<PlaybackSnapshot, String> {
        self.state
            .read()
            .map(|state| state.snapshot.clone())
            .map_err(|error| format!("playback state lock poisoned: {error}"))
    }

    pub fn integration_settings(&self) -> Result<PlaybackIntegrationSettings, String> {
        self.state
            .read()
            .map(|state| state.integrations.clone())
            .map_err(|error| format!("playback state lock poisoned: {error}"))
    }

    pub fn update_integration_settings(
        &self,
        settings: PlaybackIntegrationSettings,
    ) -> Result<PlaybackSnapshot, String> {
        let settings = settings.normalize()?;
        self.mutate(|state| {
            state.integrations = settings;
            Ok(())
        })
    }

    pub fn current_track_liked(&self) -> Result<bool, String> {
        self.state
            .read()
            .map(|state| state.current_track_liked)
            .map_err(|error| format!("playback state lock poisoned: {error}"))
    }

    pub fn set_current_track_liked(&self, liked: bool) -> Result<PlaybackSnapshot, String> {
        self.mutate(|state| {
            state.current_track_liked = liked;
            Ok(())
        })
    }

    pub fn replace_queue(&self, queue: Vec<PlaybackTrack>) -> Result<PlaybackSnapshot, String> {
        if queue.len() > MAX_QUEUE_TRACKS {
            return Err(format!(
                "playback queue exceeds the {MAX_QUEUE_TRACKS}-track limit"
            ));
        }
        let mut seen = HashSet::with_capacity(queue.len());
        let mut normalized = Vec::with_capacity(queue.len());
        for track in queue {
            let track = track.normalize()?;
            if seen.insert(track.video_id.clone()) {
                normalized.push(track);
            }
        }

        self.mutate(|state| {
            if let Some(current) = state.snapshot.current_track.as_ref() {
                if !seen.contains(&current.video_id) {
                    if normalized.len() == MAX_QUEUE_TRACKS {
                        return Err(format!(
                            "playback queue cannot preserve the current track within the \
                             {MAX_QUEUE_TRACKS}-track limit"
                        ));
                    }
                    normalized.insert(0, current.clone());
                }
            }
            state.snapshot.queue = normalized;
            if state.pending_crossfade.as_ref().is_some_and(|pending| {
                !state
                    .snapshot
                    .queue
                    .iter()
                    .any(|track| track.video_id == pending.to_track.video_id)
            }) {
                state.pending_crossfade = None;
            }
            Ok(())
        })
    }

    pub fn set_current_track(
        &self,
        track: Option<PlaybackTrack>,
    ) -> Result<PlaybackSnapshot, String> {
        let track = track.map(PlaybackTrack::normalize).transpose()?;
        self.mutate(|state| {
            let same_track = track
                .as_ref()
                .zip(state.snapshot.current_track.as_ref())
                .is_some_and(|(next, current)| next.video_id == current.video_id);
            if same_track {
                update_current_metadata(state, track.expect("same_track requires a track"));
                return Ok(());
            }

            state.snapshot.current_track = track.clone();
            state.current_track_liked = false;
            state.snapshot.playback_instance = state.snapshot.playback_instance.wrapping_add(1);
            state.snapshot.position_seconds = 0.0;
            state.snapshot.duration_seconds = track
                .as_ref()
                .and_then(|item| item.duration_seconds)
                .unwrap_or(0.0);
            state.pending_crossfade = None;
            state.failed_crossfade_from = None;

            if let Some(current) = track {
                ensure_current_is_queued(state, current)?;
                // Selecting a track does not start source loading. Keeping this Stopped makes a
                // restored session ready to play without claiming that transport work is active.
                state.snapshot.status = PlaybackStatus::Stopped;
            } else {
                state.snapshot.status = PlaybackStatus::Stopped;
            }
            Ok(())
        })
    }

    pub fn update_transport(&self, update: TransportUpdate) -> Result<PlaybackSnapshot, String> {
        super::model::validate_seconds("positionSeconds", update.position_seconds)?;
        super::model::validate_seconds("durationSeconds", update.duration_seconds)?;
        if update
            .volume
            .is_some_and(|volume| !volume.is_finite() || !(0.0..=1.0).contains(&volume))
        {
            return Err("volume must be finite and between 0 and 1".to_string());
        }
        self.mutate(|state| {
            if let Some(status) = update.status {
                state.snapshot.status = status;
            }
            if let Some(position) = update.position_seconds {
                state.snapshot.position_seconds = position;
            }
            if let Some(duration) = update.duration_seconds {
                state.snapshot.duration_seconds = duration;
            }
            if let Some(volume) = update.volume {
                state.snapshot.volume = volume;
            }
            if let Some(shuffle) = update.shuffle {
                state.snapshot.shuffle = shuffle;
            }
            if let Some(repeat) = update.repeat {
                state.snapshot.repeat = repeat;
            }
            Ok(())
        })
    }

    pub(crate) fn update_runtime_transport(
        &self,
        status: PlaybackStatus,
        position_seconds: f64,
        duration_seconds: f64,
    ) -> Result<(), String> {
        super::model::validate_seconds("positionSeconds", Some(position_seconds))?;
        super::model::validate_seconds("durationSeconds", Some(duration_seconds))?;
        let mut state = self.write_state()?;
        let snapshot = &mut state.snapshot;
        if snapshot.status == status
            && snapshot.position_seconds == position_seconds
            && snapshot.duration_seconds == duration_seconds
        {
            return Ok(());
        }
        snapshot.status = status;
        snapshot.position_seconds = position_seconds;
        snapshot.duration_seconds = duration_seconds;
        bump_revision(snapshot);
        Ok(())
    }

    pub(super) fn mutate(
        &self,
        mutation: impl FnOnce(&mut EngineState) -> Result<(), String>,
    ) -> Result<PlaybackSnapshot, String> {
        let mut state = self.write_state()?;
        let previous = state.clone();
        if let Err(error) = mutation(&mut state) {
            *state = previous;
            return Err(error);
        }
        if state.snapshot != previous.snapshot {
            bump_revision(&mut state.snapshot);
        }
        Ok(state.snapshot.clone())
    }

    pub(super) fn write_state(&self) -> Result<RwLockWriteGuard<'_, EngineState>, String> {
        self.state
            .write()
            .map_err(|error| format!("playback state lock poisoned: {error}"))
    }

    pub(super) fn read_state(&self) -> Result<RwLockReadGuard<'_, EngineState>, String> {
        self.state
            .read()
            .map_err(|error| format!("playback state lock poisoned: {error}"))
    }
}

fn update_current_metadata(state: &mut EngineState, updated: PlaybackTrack) {
    state.snapshot.current_track = Some(updated.clone());
    if let Some(queue_track) = state
        .snapshot
        .queue
        .iter_mut()
        .find(|item| item.video_id == updated.video_id)
    {
        *queue_track = updated;
    }
}

fn ensure_current_is_queued(state: &mut EngineState, current: PlaybackTrack) -> Result<(), String> {
    if state
        .snapshot
        .queue
        .iter()
        .any(|item| item.video_id == current.video_id)
    {
        return Ok(());
    }
    if state.snapshot.queue.len() == MAX_QUEUE_TRACKS {
        return Err(format!(
            "playback queue cannot add the current track beyond the \
             {MAX_QUEUE_TRACKS}-track limit"
        ));
    }
    state.snapshot.queue.insert(0, current);
    Ok(())
}

pub(super) fn set_native_current_track(
    state: &mut EngineState,
    track: PlaybackTrack,
    status: PlaybackStatus,
) {
    state.current_track_liked = false;
    state.snapshot.playback_instance = state.snapshot.playback_instance.wrapping_add(1);
    state.snapshot.position_seconds = 0.0;
    state.snapshot.duration_seconds = track.duration_seconds.unwrap_or(0.0);
    state.snapshot.current_track = Some(track);
    state.snapshot.status = status;
}

pub(super) fn bump_revision(snapshot: &mut PlaybackSnapshot) {
    snapshot.revision = snapshot.revision.wrapping_add(1);
}
