"""Background audio analysis for playlist Mix.

The analyzer deliberately works from a local, bounded PCM decode. Playback never
waits for it, and all results are cached by the YouTube audio source id.
"""

from __future__ import annotations

import subprocess
import threading
import time
import uuid
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
import sqlite3
from typing import Protocol

from src.lib.integrations.ffmpeg import FFmpeg
from src.lib.runtime.metadata_cache import MetadataCache

from .playlist_mix import PlaylistMix
from .stream import StreamService


class TrackAnalyzer(Protocol):
    def analyze(self, path: str, video_id: str) -> dict[str, object]: ...


class NumpyTrackAnalyzer:
    """Estimate tempo, key, beat locations, and usable intro/outro boundaries."""

    _SAMPLE_RATE = 11_025
    _MAX_SECONDS = 75

    def __init__(self, ffmpeg: FFmpeg) -> None:
        self._ffmpeg = ffmpeg

    def analyze(self, path: str, video_id: str) -> dict[str, object]:
        samples = self._decode(path)
        if samples.size < self._SAMPLE_RATE * 8:
            raise ValueError("audio is too short to analyze")
        onset, hop = self._onset_envelope(samples)
        bpm, confidence = self._estimate_bpm(onset, hop)
        key = self._estimate_camelot_key(samples)
        beats = self._estimate_beats(onset, hop, bpm)
        duration = samples.size / self._SAMPLE_RATE
        return {
            "videoId": video_id,
            "status": "complete",
            "bpm": round(bpm, 2),
            "camelotKey": key,
            "beatGridSeconds": beats,
            "cuePoints": {
                "introEndSeconds": round(min(16.0, duration * 0.1), 2),
                "outroStartSeconds": round(max(duration - 24.0, duration * 0.8), 2),
            },
            "confidence": round(confidence, 3),
        }

    def _decode(self, path: str) -> np.ndarray:
        import numpy as np

        executable = self._ffmpeg.exe_path()
        if not executable:
            raise RuntimeError("ffmpeg is unavailable")
        result = subprocess.run(
            [
                executable, "-v", "error", "-t", str(self._MAX_SECONDS), "-i", path,
                "-ac", "1", "-ar", str(self._SAMPLE_RATE), "-f", "f32le", "pipe:1",
            ],
            capture_output=True,
            timeout=90,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("ffmpeg could not decode the track")
        return np.frombuffer(result.stdout, dtype=np.float32)

    def _onset_envelope(self, samples: np.ndarray) -> tuple[np.ndarray, int]:
        import numpy as np

        frame, hop = 1024, 512
        usable = samples.size - frame
        if usable <= 0:
            raise ValueError("audio is too short to frame")
        frames = np.lib.stride_tricks.sliding_window_view(samples[:usable], frame)[::hop]
        spectrum = np.abs(np.fft.rfft(frames * np.hanning(frame), axis=1))
        onset = np.maximum(np.diff(spectrum, axis=0), 0).mean(axis=1)
        return onset / (onset.max() or 1.0), hop

    def _estimate_bpm(self, onset: np.ndarray, hop: int) -> tuple[float, float]:
        import numpy as np

        correlation = np.correlate(onset, onset, mode="full")[len(onset) - 1 :]
        min_lag = max(1, round(60 * self._SAMPLE_RATE / (hop * 190)))
        max_lag = min(len(correlation) - 1, round(60 * self._SAMPLE_RATE / (hop * 70)))
        if max_lag <= min_lag:
            raise ValueError("insufficient onset data")
        lag = min_lag + int(np.argmax(correlation[min_lag : max_lag + 1]))
        bpm = 60 * self._SAMPLE_RATE / (hop * lag)
        confidence = float(correlation[lag] / (correlation[0] or 1.0))
        return bpm, confidence

    def _estimate_beats(self, onset: np.ndarray, hop: int, bpm: float) -> list[float]:
        import numpy as np

        beat_frames = max(1, round(60 * self._SAMPLE_RATE / (hop * bpm)))
        first = int(np.argmax(onset[:beat_frames]))
        beats: list[float] = []
        for center in range(first, len(onset), beat_frames):
            start, end = max(0, center - 2), min(len(onset), center + 3)
            local = start + int(np.argmax(onset[start:end]))
            beats.append(round(local * hop / self._SAMPLE_RATE, 3))
            if len(beats) == 256:
                break
        return beats

    def _estimate_camelot_key(self, samples: np.ndarray) -> str:
        import numpy as np

        frame = 4096
        usable = samples.size - frame
        if usable <= 0:
            return "Unknown"
        windows = np.lib.stride_tricks.sliding_window_view(samples[:usable], frame)[::frame]
        spectrum = np.abs(np.fft.rfft(windows * np.hanning(frame), axis=1)).mean(axis=0)
        frequencies = np.fft.rfftfreq(frame, 1 / self._SAMPLE_RATE)
        valid = frequencies > 40
        midi = np.rint(69 + 12 * np.log2(frequencies[valid] / 440)).astype(int)
        chroma = np.bincount(midi % 12, weights=spectrum[valid], minlength=12)
        major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor = np.array([6.33, 2.68, 3.52, 5.38, 2.6, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        scores = [(float(np.dot(chroma, np.roll(template, root))), root, mode) for mode, template in (("major", major), ("minor", minor)) for root in range(12)]
        _, root, mode = max(scores)
        minor_codes = ["5A", "12A", "7A", "2A", "9A", "4A", "11A", "6A", "1A", "8A", "3A", "10A"]
        major_codes = ["8B", "3B", "10B", "5B", "12B", "7B", "2B", "9B", "4B", "11B", "6B", "1B"]
        return (major_codes if mode == "major" else minor_codes)[root]


class MixAnalysisService:
    """Owns one-at-a-time playlist analysis jobs and source-level caching."""

    _CATEGORY = "mix_audio_analysis"
    _TERMINAL_STATUSES = {"complete", "failed", "cancelled"}
    # How long a finished job (and its full per-track analysis payload) stays fetchable via
    # get_job() before being dropped. Long enough for a client to poll and see the final
    # status; short enough that repeated playlist re-analysis over a session cannot grow
    # `_jobs`/`_cancel_events` without bound.
    _JOB_RETENTION_SECONDS = 15 * 60

    def __init__(self, stream_service: StreamService, metadata_cache: MetadataCache, playlist_mix: PlaylistMix, analyzer: TrackAnalyzer) -> None:
        self._stream_service = stream_service
        self._metadata_cache = metadata_cache
        self._playlist_mix = playlist_mix
        self._analyzer = analyzer
        self._jobs: dict[str, dict[str, object]] = {}
        self._active_jobs: dict[tuple[str, str], str] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[None]] = {}
        self._lock = threading.Lock()
        # Audio decoding and NumPy analysis are CPU-intensive. One worker keeps
        # rapid playlist updates from multiplying that work across CPU cores.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mix-analysis")

    def start(self, profile_name: str | None, playlist_id: str, tracks: list[dict[str, str]]) -> dict[str, object]:
        profile_key = profile_name or "default"
        active_key = (profile_key, playlist_id)
        signature = tuple((track["instanceId"], track["videoId"]) for track in tracks)
        job_id = uuid.uuid4().hex
        job = {
            "jobId": job_id,
            "playlistId": playlist_id,
            "_profile": profile_key,
            "_signature": signature,
            "status": "queued",
            "total": len(tracks),
            "completed": 0,
            "tracks": {},
        }
        with self._lock:
            self._prune_stale_jobs_locked(time.time())
            active_job_id = self._active_jobs.get(active_key)
            active_job = self._jobs.get(active_job_id) if active_job_id else None
            if active_job and active_job["status"] in {"queued", "running"}:
                if active_job["_signature"] == signature:
                    return self._public_job(active_job)
                self._cancel_events[active_job_id].set()
                active_job["status"] = "cancelled"
                active_job["_finished_at"] = time.time()
                if future := self._futures.get(active_job_id):
                    if future.cancel():
                        del self._futures[active_job_id]
            self._jobs[job_id] = job
            self._cancel_events[job_id] = threading.Event()
            self._active_jobs[active_key] = job_id
            future = self._executor.submit(self._run, job_id, profile_name, playlist_id, tracks)
            self._futures[job_id] = future
            if future.done():
                self._futures.pop(job_id, None)
        return self._public_job(job)

    def get_job(self, profile_name: str | None, playlist_id: str, job_id: str) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["playlistId"] != playlist_id or job["_profile"] != (profile_name or "default"):
                return None
            return self._public_job(job)

    def _run(self, job_id: str, profile_name: str | None, playlist_id: str, tracks: list[dict[str, str]]) -> None:
        try:
            if self._is_cancelled(job_id):
                return
            results: dict[str, dict[str, object]] = {}
            self._update_job(job_id, status="running")
            for track in tracks:
                if self._is_cancelled(job_id):
                    return
                result = self._analyze_track(track["videoId"])
                if self._is_cancelled(job_id):
                    return
                results[track["instanceId"]] = result
                self._playlist_mix.store_analysis(profile_name, playlist_id, tracks, results)
                self._update_job(job_id, completed=len(results), tracks=dict(results))
            self._update_job(job_id, status="complete")
        except sqlite3.Error:
            self._update_job(job_id, status="failed", error="analysis cache unavailable")
        finally:
            with self._lock:
                self._futures.pop(job_id, None)
                job = self._jobs.get(job_id)
                if job and self._active_jobs.get((job["_profile"], playlist_id)) == job_id:
                    del self._active_jobs[(job["_profile"], playlist_id)]

    def _is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._cancel_events[job_id].is_set()

    @staticmethod
    def _public_job(job: Mapping[str, object]) -> dict[str, object]:
        return {key: value for key, value in job.items() if not key.startswith("_")}

    def _analyze_track(self, video_id: str) -> dict[str, object]:
        cache_key = f"v1:{video_id}"
        cached = self._metadata_cache.get(self._CATEGORY, cache_key)
        if cached is not None:
            return cached
        payload, status = self._stream_service.prepare_download(video_id)
        if status != 200 or not isinstance(payload.get("path"), str):
            return {"videoId": video_id, "status": "unavailable"}
        try:
            result = self._analyzer.analyze(payload["path"], video_id)
        except (ImportError, OSError, RuntimeError, ValueError, subprocess.SubprocessError):
            return {"videoId": video_id, "status": "failed"}
        self._metadata_cache.put(self._CATEGORY, cache_key, result)
        return result

    def _update_job(self, job_id: str, **updates: object) -> None:
        with self._lock:
            if job := self._jobs.get(job_id):
                job.update(updates)
                if updates.get("status") in self._TERMINAL_STATUSES:
                    job["_finished_at"] = time.time()

    def _prune_stale_jobs_locked(self, now: float) -> None:
        """Drop terminal jobs past their retention window. Caller must hold ``_lock``.

        ``_run``'s ``finally`` already clears ``_futures``/``_active_jobs``, but nothing
        previously cleared ``_jobs``/``_cancel_events`` — every job leaked its entry (including
        the full per-track analysis payload) for the life of the process.
        """
        stale = [
            job_id
            for job_id, job in self._jobs.items()
            if isinstance(job.get("_finished_at"), (int, float))
            and now - job["_finished_at"] > self._JOB_RETENTION_SECONDS
        ]
        for job_id in stale:
            del self._jobs[job_id]
            self._cancel_events.pop(job_id, None)
