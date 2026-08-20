use std::collections::HashMap;

use super::model::{
    CrossfadeOverride, CrossfadeRequest, MixTransition, PlaybackSnapshot, PlaybackSourceRequest,
    PlaybackStatus, PlaybackTrack, RepeatMode, TransitionPolicyUpdate,
};
use super::state::{bump_revision, set_native_current_track, EngineState, PlaybackEngine};

pub(crate) const MAX_CROSSFADE_SECONDS: f64 = 60.0;

impl PlaybackEngine {
    pub fn update_transition_policy(
        &self,
        update: TransitionPolicyUpdate,
    ) -> Result<PlaybackSnapshot, String> {
        validate_crossfade_seconds(update.crossfade_seconds)?;
        let overrides = update
            .crossfade_overrides
            .map(normalize_crossfade_overrides)
            .transpose()?;
        let mix_transitions = update
            .mix_transitions
            .map(normalize_mix_transitions)
            .transpose()?;

        self.mutate(|state| {
            if let Some(seconds) = update.crossfade_seconds {
                state.policy.crossfade_seconds = seconds;
            }
            if let Some(overrides) = overrides {
                state.policy.crossfade_overrides = overrides;
            }
            if let Some(progressive) = update.progressive {
                state.policy.progressive = progressive;
            }
            if let Some(enabled) = update.automatic_crossfade {
                state.policy.automatic_crossfade = enabled;
                if !enabled {
                    state.pending_crossfade = None;
                }
            }
            if let Some(mix_transitions) = mix_transitions {
                state.policy.mix_transitions = mix_transitions;
            }
            if let Some(enabled) = update.mix_enabled {
                state.policy.mix_enabled = enabled;
            }
            if let Some(enabled) = update.mix_tempo_lock {
                state.policy.mix_tempo_lock = enabled;
            }
            Ok(())
        })
    }

    pub fn prepare_crossfade(
        &self,
        position_seconds: f64,
        duration_seconds: f64,
    ) -> Result<Option<CrossfadeRequest>, String> {
        super::model::validate_seconds("positionSeconds", Some(position_seconds))?;
        super::model::validate_seconds("durationSeconds", Some(duration_seconds))?;

        // This is polled every ~20ms for the whole track, so try it under a read lock first: the
        // common case (not yet near the end of the track) bails out here without ever taking the
        // write lock, which would otherwise block every other reader/writer of engine state. The
        // guard is scoped so it's released before a possible write-lock acquisition below.
        {
            let state = self.read_state()?;
            if evaluate_pending_crossfade(&state, position_seconds, duration_seconds).is_none() {
                return Ok(None);
            }
        }

        // It looked due under the read lock; re-validate under the write lock since state may
        // have changed in between (a concurrent seek, track change, or another crossfade already
        // committed) before actually committing to it.
        let mut state = self.write_state()?;
        let Some((current, next, seconds)) =
            evaluate_pending_crossfade(&state, position_seconds, duration_seconds)
        else {
            return Ok(None);
        };
        let mix_transition = state
            .policy
            .mix_enabled
            .then(|| {
                state
                    .policy
                    .mix_transitions
                    .get(&(current.video_id.clone(), next.video_id.clone()))
                    .cloned()
            })
            .flatten();
        let request = CrossfadeRequest {
            from_track: current,
            to_track: next,
            seconds,
            progressive: state.policy.progressive,
            mix_transition,
            mix_tempo_lock: state.policy.mix_tempo_lock,
        };
        state.pending_crossfade = Some(request.clone());
        Ok(Some(request))
    }

    pub fn commit_crossfade(
        &self,
        status: PlaybackStatus,
    ) -> Result<Option<PlaybackTrack>, String> {
        let mut state = self.write_state()?;
        let Some(pending) = state.pending_crossfade.take() else {
            return Ok(None);
        };
        if state
            .snapshot
            .current_track
            .as_ref()
            .map(|track| &track.video_id)
            != Some(&pending.from_track.video_id)
        {
            return Ok(None);
        }
        set_native_current_track(&mut state, pending.to_track.clone(), status);
        state.failed_crossfade_from = None;
        bump_revision(&mut state.snapshot);
        Ok(Some(pending.to_track))
    }

    pub fn fail_crossfade(&self) -> Result<(), String> {
        let mut state = self.write_state()?;
        if let Some(pending) = state.pending_crossfade.take() {
            state.failed_crossfade_from = Some(pending.from_track.video_id);
        }
        Ok(())
    }

    pub fn cancel_crossfade(&self) -> Result<(), String> {
        let mut state = self.write_state()?;
        state.pending_crossfade = None;
        state.failed_crossfade_from = None;
        Ok(())
    }

    pub fn advance_after_end(&self) -> Result<Option<PlaybackSourceRequest>, String> {
        let mut state = self.write_state()?;
        let pending_target = state
            .pending_crossfade
            .take()
            .map(|pending| pending.to_track);
        let next = if state.snapshot.repeat == RepeatMode::One {
            state.snapshot.current_track.clone()
        } else {
            pending_target.or_else(|| choose_next_track(&mut state))
        };
        state.failed_crossfade_from = None;

        let Some(track) = next else {
            state.snapshot.status = PlaybackStatus::Stopped;
            state.snapshot.position_seconds = 0.0;
            state.snapshot.duration_seconds = 0.0;
            bump_revision(&mut state.snapshot);
            return Ok(None);
        };
        set_native_current_track(&mut state, track.clone(), PlaybackStatus::Loading);
        let progressive = state.policy.progressive;
        bump_revision(&mut state.snapshot);
        Ok(Some(PlaybackSourceRequest { track, progressive }))
    }

    pub fn select_next(&self) -> Result<Option<PlaybackSourceRequest>, String> {
        self.select_manual_track(ManualDirection::Next)
    }

    pub fn select_previous(&self) -> Result<Option<PlaybackSourceRequest>, String> {
        self.select_manual_track(ManualDirection::Previous)
    }

    pub fn select_track(&self, video_id: &str) -> Result<Option<PlaybackSourceRequest>, String> {
        super::model::validate_video_id("videoId", video_id)?;
        let mut state = self.write_state()?;
        let Some(track) = state
            .snapshot
            .queue
            .iter()
            .find(|track| track.video_id == video_id)
            .cloned()
        else {
            return Ok(None);
        };
        state.pending_crossfade = None;
        state.failed_crossfade_from = None;
        set_native_current_track(&mut state, track.clone(), PlaybackStatus::Loading);
        let progressive = state.policy.progressive;
        bump_revision(&mut state.snapshot);
        Ok(Some(PlaybackSourceRequest { track, progressive }))
    }

    pub fn restart_current(&self) -> Result<Option<PlaybackSourceRequest>, String> {
        let mut state = self.write_state()?;
        let Some(track) = state.snapshot.current_track.clone() else {
            return Ok(None);
        };
        state.pending_crossfade = None;
        state.failed_crossfade_from = None;
        set_native_current_track(&mut state, track.clone(), PlaybackStatus::Loading);
        let progressive = state.policy.progressive;
        bump_revision(&mut state.snapshot);
        Ok(Some(PlaybackSourceRequest { track, progressive }))
    }

    fn select_manual_track(
        &self,
        direction: ManualDirection,
    ) -> Result<Option<PlaybackSourceRequest>, String> {
        let mut state = self.write_state()?;
        let Some(current) = state.snapshot.current_track.as_ref() else {
            return Ok(None);
        };
        let Some(current_index) = state
            .snapshot
            .queue
            .iter()
            .position(|track| track.video_id == current.video_id)
        else {
            return Ok(None);
        };
        if state.snapshot.queue.is_empty() {
            return Ok(None);
        }

        let next_index = match direction {
            ManualDirection::Next => (current_index + 1) % state.snapshot.queue.len(),
            ManualDirection::Previous => {
                (current_index + state.snapshot.queue.len() - 1) % state.snapshot.queue.len()
            }
        };
        let track = state.snapshot.queue[next_index].clone();
        state.pending_crossfade = None;
        state.failed_crossfade_from = None;
        set_native_current_track(&mut state, track.clone(), PlaybackStatus::Loading);
        let progressive = state.policy.progressive;
        bump_revision(&mut state.snapshot);
        Ok(Some(PlaybackSourceRequest { track, progressive }))
    }
}

#[derive(Clone, Copy)]
enum ManualDirection {
    Next,
    Previous,
}

// Shared by the read-locked fast path and the write-locked commit path in `prepare_crossfade` so
// eligibility is computed identically (and only once) by each.
fn evaluate_pending_crossfade(
    state: &EngineState,
    position_seconds: f64,
    duration_seconds: f64,
) -> Option<(PlaybackTrack, PlaybackTrack, f64)> {
    if transition_is_blocked(state, duration_seconds) {
        return None;
    }
    let current = state.snapshot.current_track.clone()?;
    if state.failed_crossfade_from.as_deref() == Some(current.video_id.as_str()) {
        return None;
    }
    let next = peek_next_track(state)?;
    let seconds = transition_seconds(state, &current, &next);
    let remaining = duration_seconds - position_seconds;
    if seconds <= 0.0 || remaining > seconds || remaining <= 0.05 {
        return None;
    }
    Some((current, next, seconds))
}

fn transition_is_blocked(state: &EngineState, duration_seconds: f64) -> bool {
    !state.policy.automatic_crossfade
        || state.pending_crossfade.is_some()
        || state.snapshot.repeat == RepeatMode::One
        || duration_seconds <= 0.0
}

fn transition_seconds(state: &EngineState, current: &PlaybackTrack, next: &PlaybackTrack) -> f64 {
    state
        .policy
        .crossfade_overrides
        .get(&(current.video_id.clone(), next.video_id.clone()))
        .copied()
        .unwrap_or(state.policy.crossfade_seconds)
}

fn choose_next_track(state: &mut EngineState) -> Option<PlaybackTrack> {
    peek_next_track(state)
}

fn peek_next_track(state: &EngineState) -> Option<PlaybackTrack> {
    let current = state.snapshot.current_track.as_ref()?;
    let current_index = state
        .snapshot
        .queue
        .iter()
        .position(|track| track.video_id == current.video_id)?;
    if let Some(next) = state.snapshot.queue.get(current_index + 1) {
        return Some(next.clone());
    }
    (state.snapshot.repeat == RepeatMode::All)
        .then(|| state.snapshot.queue.first().cloned())
        .flatten()
}

fn normalize_crossfade_overrides(
    overrides: Vec<CrossfadeOverride>,
) -> Result<HashMap<(String, String), f64>, String> {
    let mut normalized = HashMap::with_capacity(overrides.len());
    for item in overrides {
        super::model::validate_video_id("fromVideoId", &item.from_video_id)?;
        super::model::validate_video_id("toVideoId", &item.to_video_id)?;
        validate_crossfade_seconds(Some(item.seconds))?;
        normalized.insert((item.from_video_id, item.to_video_id), item.seconds);
    }
    Ok(normalized)
}

fn normalize_mix_transitions(
    transitions: Vec<MixTransition>,
) -> Result<HashMap<(String, String), MixTransition>, String> {
    let mut normalized = HashMap::with_capacity(transitions.len());
    for item in transitions {
        super::model::validate_video_id("fromVideoId", &item.from_video_id)?;
        super::model::validate_video_id("toVideoId", &item.to_video_id)?;
        if !matches!(item.bars, 2 | 4 | 8) {
            return Err("mix transition bars must be 2, 4, or 8".to_string());
        }
        if !item.beat_offset_ms.is_finite() || !(-100.0..=100.0).contains(&item.beat_offset_ms) {
            return Err(
                "mix transition beatOffsetMs must be finite and between -100 and 100".to_string(),
            );
        }
        for (name, bpm) in [("fromBpm", item.from_bpm), ("toBpm", item.to_bpm)] {
            if bpm.is_some_and(|value| !value.is_finite() || !(40.0..=300.0).contains(&value)) {
                return Err(format!("mix transition {name} must be between 40 and 300"));
            }
        }
        normalized.insert((item.from_video_id.clone(), item.to_video_id.clone()), item);
    }
    Ok(normalized)
}

fn validate_crossfade_seconds(value: Option<f64>) -> Result<(), String> {
    if value.is_some_and(|seconds| {
        !seconds.is_finite() || !(0.0..=MAX_CROSSFADE_SECONDS).contains(&seconds)
    }) {
        return Err(format!(
            "crossfade seconds must be finite and between 0 and {MAX_CROSSFADE_SECONDS}"
        ));
    }
    Ok(())
}
