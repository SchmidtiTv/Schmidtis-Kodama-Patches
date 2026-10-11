//! Room transport remains native. The webview supplies clock-corrected room observations;
//! the audio loop prepares, schedules and corrects the actual source.
use serde::Deserialize;
use tauri::Emitter;

use super::model::{PlaybackSnapshot, PlaybackSourceRequest, PlaybackStatus, PlaybackTrack};
use super::state::{bump_revision, set_native_current_track, PlaybackEngine};
use crate::audio::player::{AudioCmd, AudioPlayer};

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TogetherPlaybackState {
    pub track: Option<PlaybackTrack>,
    pub playing: bool,
    pub pos: f64,
    pub at: f64,
    #[serde(default = "normal_rate")]
    pub rate: f64,
}
fn normal_rate() -> f64 {
    1.0
}

impl TogetherPlaybackState {
    fn validate(mut self) -> Result<Self, String> {
        if !self.pos.is_finite()
            || self.pos < 0.0
            || !self.at.is_finite()
            || !self.rate.is_finite()
            || !(0.98..=1.02).contains(&self.rate)
        {
            return Err("invalid room playback clock".into());
        }
        self.track = self.track.map(PlaybackTrack::normalize).transpose()?;
        Ok(self)
    }
    fn position_at(&self, now: f64) -> f64 {
        self.pos
            + if self.playing {
                (now - self.at).max(0.0) / 1000.0 * self.rate
            } else {
                0.0
            }
    }
}

#[derive(Clone, Debug, Default)]
pub(super) struct TogetherState {
    pub active: bool,
    pub listener: bool,
    target: Option<TogetherPlaybackState>,
    prepared: Option<(f64, f64)>, // local start time and prepared position
    rate: f32,
    latency_ms: f64,
    seek_above_ms: f64,
    max_rate: f64,
    ahead_ms: f64,
    retry_load_at_ms: f64,
}

impl PlaybackEngine {
    pub fn should_hold_together_source(&self) -> bool {
        self.read_state()
            .map(|state| {
                state.together.active
                    && (state.together.listener || state.together.target.is_some())
            })
            .unwrap_or(false)
    }

    pub fn require_local_transport(&self) -> Result<(), String> {
        if self.read_state()?.together.listener {
            return Err("playback is controlled by the room host".into());
        }
        Ok(())
    }

    pub fn set_together(
        &self,
        active: bool,
        listener: bool,
        invite_url: Option<String>,
    ) -> Result<PlaybackSnapshot, String> {
        if let Some(url) = invite_url.as_ref() {
            if !url.starts_with("https://kodama.kiyoshi.dev/together/?")
                || !url
                    .trim_start_matches("https://kodama.kiyoshi.dev/together/?")
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric())
            {
                return Err("invalid room invite URL".into());
            }
        }
        self.mutate(|state| {
            let next_listener = active && listener;
            if state.together.active != active
                || state.together.listener != next_listener
                || !active
            {
                state.together.target = None;
                state.together.prepared = None;
                state.together.rate = 1.0;
            }
            if state.together.ahead_ms < 1500.0 {
                state.together.ahead_ms = 1500.0;
            }
            state.together.active = active;
            state.together.listener = next_listener;
            state.integrations.together_invite_url = if active { invite_url } else { None };
            if next_listener {
                state.pending_crossfade = None;
            }
            Ok(())
        })
    }

    pub fn update_together_target(
        &self,
        target: TogetherPlaybackState,
        latency_ms: f64,
        seek_above_ms: f64,
        max_rate: f64,
    ) -> Result<PlaybackSnapshot, String> {
        let target = target.validate()?;
        if !latency_ms.is_finite()
            || !(-2000.0..=5000.0).contains(&latency_ms)
            || !seek_above_ms.is_finite()
            || !(50.0..=10000.0).contains(&seek_above_ms)
            || !max_rate.is_finite()
            || !(0.0..=20.0).contains(&max_rate)
        {
            return Err("invalid room synchronization tuning".into());
        }
        self.mutate(|state| {
            if !state.together.active {
                return Err("no active room".into());
            }
            state.together.target = Some(target);
            state.together.latency_ms = latency_ms;
            state.together.seek_above_ms = seek_above_ms;
            state.together.max_rate = max_rate;
            Ok(())
        })
    }

    /// Called by the audio thread even when the main webview is hidden. `preparing` is true
    /// until a source or seek has completed; scheduling never races an unfinished source.
    pub fn together_audio_commands(
        &self,
        now_ms: f64,
        preparing: bool,
    ) -> Result<Vec<AudioCmd>, String> {
        let mut state = self.write_state()?;
        if !state.together.active {
            return Ok(Vec::new());
        }
        let Some(target) = state.together.target.clone() else {
            return Ok(Vec::new());
        };
        let Some(track) = target.track.as_ref() else {
            state.together.prepared = None;
            if state.snapshot.status == PlaybackStatus::Playing {
                return Ok(vec![AudioCmd::Pause, AudioCmd::SetRate(1.0)]);
            }
            return Ok(Vec::new());
        };
        if state.snapshot.current_track.as_ref().map(|t| &t.video_id) != Some(&track.video_id)
            || state.snapshot.status == PlaybackStatus::Stopped
        {
            let same_track =
                state.snapshot.current_track.as_ref().map(|t| &t.video_id) == Some(&track.video_id);
            if same_track && now_ms < state.together.retry_load_at_ms {
                return Ok(Vec::new());
            }
            state.together.retry_load_at_ms = now_ms + 10000.0;
            set_native_current_track(&mut state, track.clone(), PlaybackStatus::Paused);
            if !state
                .snapshot
                .queue
                .iter()
                .any(|t| t.video_id == track.video_id)
            {
                state.snapshot.queue.insert(0, track.clone());
            }
            state.pending_crossfade = None;
            state.together.prepared = None;
            bump_revision(&mut state.snapshot);
            return Ok(vec![
                AudioCmd::Pause,
                AudioCmd::SetRate(1.0),
                AudioCmd::PlayResolved {
                    request: PlaybackSourceRequest {
                        track: track.clone(),
                        progressive: state.policy.progressive,
                    },
                },
            ]);
        }
        if preparing {
            return Ok(Vec::new());
        }
        if !state.together.listener
            && now_ms > target.at + 300.0
            && state.snapshot.status == PlaybackStatus::Playing
        {
            state.together.target = None;
            state.together.prepared = None;
            return Ok(vec![AudioCmd::SetRate(1.0)]);
        }
        let position = state.snapshot.position_seconds;
        let paused = state.snapshot.status != PlaybackStatus::Playing;
        let latency = state.together.latency_ms / 1000.0;
        if !target.playing {
            state.together.prepared = None;
            state.together.rate = 1.0;
            let mut commands = vec![AudioCmd::SetRate(1.0)];
            if !paused {
                commands.push(AudioCmd::Pause);
            }
            if (position - target.pos).abs() > 0.05 {
                commands.push(AudioCmd::Seek(target.pos));
            }
            return Ok(commands);
        }
        if let Some((start, prepared)) = state.together.prepared {
            let moved = (target.position_at(start) + latency - prepared).abs();
            if moved * 1000.0 <= state.together.seek_above_ms {
                if now_ms < start + 300.0 {
                    return Ok(Vec::new());
                }
                if paused && now_ms > start + 100.0 {
                    state.together.ahead_ms =
                        ((state.together.ahead_ms + now_ms - start) * 1.3).min(6000.0);
                }
                state.together.prepared = None;
            } else {
                state.together.prepared = None;
            }
        }
        let wanted = (target.position_at(now_ms) + latency).max(0.0);
        if state.snapshot.duration_seconds > 0.0 && wanted > state.snapshot.duration_seconds - 0.5 {
            return Ok(vec![AudioCmd::SetRate(1.0)]);
        }
        let drift = position - wanted;
        if paused || drift.abs() * 1000.0 > state.together.seek_above_ms {
            let start = (now_ms + state.together.ahead_ms).max(target.at);
            let position = (target.position_at(start) + latency).max(0.0);
            state.together.prepared = Some((start, position));
            state.together.rate = 1.0;
            return Ok(vec![
                AudioCmd::Pause,
                AudioCmd::SetRate(1.0),
                AudioCmd::Seek(position),
                AudioCmd::ResumeAt(start),
            ]);
        }
        let correction = if drift.abs() < 0.01 {
            0.0
        } else {
            (-drift / 10.0).clamp(
                -state.together.max_rate / 1000.0,
                state.together.max_rate / 1000.0,
            )
        };
        let rate = (target.rate + correction) as f32;
        if (rate - state.together.rate).abs() < 0.0001 {
            return Ok(Vec::new());
        }
        state.together.rate = rate;
        Ok(vec![AudioCmd::SetRate(rate)])
    }
}

#[tauri::command]
pub fn player_set_together(
    app: tauri::AppHandle,
    engine: tauri::State<'_, PlaybackEngine>,
    audio: tauri::State<'_, AudioPlayer>,
    active: bool,
    listener: bool,
    invite_url: Option<String>,
) -> Result<PlaybackSnapshot, String> {
    let previous = engine.read_state()?.together.clone();
    let snapshot = engine.set_together(active, listener, invite_url)?;
    for command in room_transition_commands(previous.active, previous.listener, active, listener) {
        audio
            .sender()?
            .send(command)
            .map_err(|error| error.to_string())?;
    }
    let _ = app.emit("playback-state-changed", &snapshot);
    Ok(snapshot)
}

#[tauri::command]
pub fn player_together_sync(
    engine: tauri::State<'_, PlaybackEngine>,
    state: TogetherPlaybackState,
    latency_ms: f64,
    seek_above_ms: f64,
    max_rate: f64,
) -> Result<PlaybackSnapshot, String> {
    engine.update_together_target(state, latency_ms, seek_above_ms, max_rate)
}

// Role changes cancel the old room's deadline without interrupting an already playing host.
fn room_transition_commands(
    was_active: bool,
    was_listener: bool,
    active: bool,
    listener: bool,
) -> Vec<AudioCmd> {
    let listener = active && listener;
    if was_active == active && was_listener == listener {
        return Vec::new();
    }
    let mut commands = vec![AudioCmd::CancelScheduledResume, AudioCmd::SetRate(1.0)];
    if (was_listener && !active) || (listener && !was_listener) {
        commands.push(AudioCmd::Pause);
    }
    commands
}

#[cfg(test)]
mod role_transition_tests {
    use super::*;
    #[test]
    fn promotion_and_host_departure_cancel_deadlines_without_pausing_playback() {
        for transition in [(true, true, true, false), (true, false, false, false)] {
            let commands =
                room_transition_commands(transition.0, transition.1, transition.2, transition.3);
            assert!(commands
                .iter()
                .any(|command| matches!(command, AudioCmd::CancelScheduledResume)));
            assert!(!commands
                .iter()
                .any(|command| matches!(command, AudioCmd::Pause)));
        }
        assert!(room_transition_commands(true, true, true, true).is_empty());
    }
    #[test]
    fn entering_or_leaving_listener_role_cancels_and_holds_transport() {
        for transition in [(true, false, true, true), (true, true, false, false)] {
            let commands =
                room_transition_commands(transition.0, transition.1, transition.2, transition.3);
            assert!(matches!(
                commands.first(),
                Some(AudioCmd::CancelScheduledResume)
            ));
            assert!(commands
                .iter()
                .any(|command| matches!(command, AudioCmd::Pause)));
        }
    }
}
