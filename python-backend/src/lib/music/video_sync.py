"""Resolve and synchronize song/official-video counterpart releases."""

import contextlib
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import numpy as np

from src.config import config_dirs, config_ytdlp
from src.lib.integrations.ffmpeg import FFmpeg
from src.lib.integrations.ytdlp import YTDLP, is_hard_error, is_unavailable
from src.lib.music.youtube_music import YoutubeMusicSession


class VideoSyncService:
    """Compute counterpart offsets and resolve quality-capped video streams."""

    CLIP_SECONDS = 100
    MAX_LAG_SECONDS = 30

    def __init__(
        self,
        music_session: YoutubeMusicSession,
        ytdlp: YTDLP,
        ffmpeg: FFmpeg,
        cache_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._music_session = music_session
        self._ytdlp = ytdlp
        self._ffmpeg = ffmpeg
        self._cache_dir = cache_dir or config_dirs.VIDEO_SYNC_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logger or logging.getLogger(__name__)
        self._path_lock = threading.Lock()
        self._offset_lock = threading.Lock()

    def _cache_path(self, video_id: str) -> Path:
        key = hashlib.md5(video_id.encode(), usedforsecurity=False).hexdigest()
        return self._cache_dir / f"{key}.json"

    def _download_clip(self, video_id: str, output_wav: Path, ffmpeg_dir: str | None) -> None:
        import yt_dlp
        from yt_dlp.utils import download_range_func

        raw_template = str(output_wav.with_name(f"{output_wav.stem}_raw.%(ext)s"))
        last_error: Exception | None = None
        # The caller adds the bundled FFmpeg directory to PATH once while both clips are
        # downloading. yt-dlp checks PATH (rather than ffmpeg_location) for ranged downloads.
        for audio_format, extra, anonymous in config_ytdlp.STREAM_ATTEMPTS:
            try:
                options: dict[str, object] = {
                    "format": audio_format,
                    "quiet": True,
                    "no_warnings": True,
                    "outtmpl": raw_template,
                    "download_ranges": download_range_func([], [(0, self.CLIP_SECONDS)]),
                    "force_keyframes_at_cuts": True,
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
                }
                if extra:
                    options.update(extra)
                if ffmpeg_dir:
                    options["ffmpeg_location"] = ffmpeg_dir
                if not anonymous:
                    self._ytdlp.apply_active_session_auth(options)
                with yt_dlp.YoutubeDL(cast("yt_dlp._Params", options)) as ydl:
                    ydl.download([f"https://music.youtube.com/watch?v={video_id}"])
                last_error = None
                break
            except Exception as error:
                last_error = error
                if is_hard_error(str(error)):
                    break
                self._logger.warning(
                    "[video-sync] %s format=%s authenticated=%s: %s",
                    video_id,
                    audio_format,
                    not anonymous,
                    error,
                )

        if last_error:
            raise last_error

        raw_wav = next(output_wav.parent.glob(f"{output_wav.stem}_raw.*"), None)
        if raw_wav is None:
            raise RuntimeError(f"no audio produced for {video_id}")
        ffmpeg_exe = self._ffmpeg.exe_path()
        if not ffmpeg_exe:
            raise RuntimeError("ffmpeg not found")
        result = subprocess.run(
            [ffmpeg_exe, "-y", "-i", str(raw_wav), "-ac", "1", "-ar", "8000", str(output_wav)],
            capture_output=True,
            timeout=60,
            creationflags=0x08000000 if os.name == "nt" else 0,
            check=False,
        )
        raw_wav.unlink(missing_ok=True)
        if result.returncode != 0 or not output_wav.exists():
            raise RuntimeError("ffmpeg failed to prepare video-sync audio")

    @staticmethod
    def _compute_offset(song_wav: Path, video_wav: Path) -> tuple[float, float]:
        from scipy.io import wavfile
        from scipy.signal import fftconvolve

        song_rate, song = wavfile.read(song_wav)
        video_rate, video = wavfile.read(video_wav)
        if song_rate != video_rate:
            raise RuntimeError(f"sample rate mismatch: {song_rate} vs {video_rate}")

        def envelope(samples: object) -> np.ndarray:
            values = np.asarray(samples).astype(np.float64)
            window = max(1, int(song_rate * 0.05))
            count = len(values) // window
            if count == 0:
                raise RuntimeError("video-sync clip is empty")
            values = values[: count * window].reshape(count, window)
            rms = np.sqrt(np.mean(values**2, axis=1))
            rms -= rms.mean()
            deviation = rms.std()
            return rms / deviation if deviation > 1e-9 else rms

        song_envelope = envelope(song)
        video_envelope = envelope(video)
        correlation = fftconvolve(video_envelope, song_envelope[::-1], mode="full")
        lags = np.arange(-len(song_envelope) + 1, len(video_envelope))
        seconds_per_window = 0.05
        mask = np.abs(lags) <= int(VideoSyncService.MAX_LAG_SECONDS / seconds_per_window)
        bounded_correlation = correlation[mask]
        bounded_lags = lags[mask]
        peak_index = int(np.argmax(bounded_correlation))
        peak_value = bounded_correlation[peak_index]
        offset_seconds = float(bounded_lags[peak_index] * seconds_per_window)
        noise = np.delete(
            bounded_correlation,
            range(max(0, peak_index - 3), min(len(bounded_correlation), peak_index + 4)),
        )
        noise_floor = float(np.abs(noise).mean()) if len(noise) else 1.0
        confidence = float(abs(peak_value) / noise_floor) if noise_floor > 1e-9 else 0.0
        return offset_seconds, confidence

    def resolve_offset(self, video_id: str) -> dict[str, object]:
        """Resolve the linked official video and calculate its audio offset."""
        cache_path = self._cache_path(video_id)
        with self._offset_lock:
            if cache_path.exists():
                try:
                    return cast(
                        "dict[str, object]", json.loads(cache_path.read_text(encoding="utf-8"))
                    )
                except (OSError, ValueError, TypeError):
                    pass

            result: dict[str, object] = {"available": False}
            try:
                watch = self._music_session.get_system_client().get_watch_playlist(
                    videoId=video_id, limit=1
                )
                raw_tracks = watch.get("tracks")
                tracks = raw_tracks if isinstance(raw_tracks, list) else []
                first_track = tracks[0] if tracks and isinstance(tracks[0], dict) else {}
                raw_counterpart = first_track.get("counterpart")
                counterpart = raw_counterpart if isinstance(raw_counterpart, dict) else None
                counterpart_id = counterpart.get("videoId") if counterpart else None
                if not counterpart_id:
                    # Some uploads are videos themselves rather than audio releases with a
                    # separate official-video counterpart. Their existing audio clock can drive
                    # the same muted video at offset zero without cross-correlation.
                    video_type = first_track.get("videoType") or ""
                    if video_type and video_type != "MUSIC_VIDEO_TYPE_ATV":
                        result = {
                            "available": True,
                            "counterpartVideoId": video_id,
                            "offsetSeconds": 0,
                            "confidence": 999,
                            "selfVideo": True,
                        }
                else:
                    ffmpeg_dir = self._ffmpeg.find()
                    if not isinstance(ffmpeg_dir, str):
                        result = {"available": False, "error": "ffmpeg not found"}
                    else:
                        temp_dir = Path(tempfile.mkdtemp())
                        try:
                            song_wav = temp_dir / "song.wav"
                            video_wav = temp_dir / "video.wav"
                            # The downloads are independent. Keep PATH stable for yt-dlp's ranged
                            # download check, then fetch them concurrently to avoid serial latency.
                            with self._path_lock:
                                old_path = os.environ.get("PATH", "")
                                if ffmpeg_dir and ffmpeg_dir not in old_path.split(os.pathsep):
                                    os.environ["PATH"] = ffmpeg_dir + os.pathsep + old_path
                                try:
                                    with ThreadPoolExecutor(max_workers=2) as pool:
                                        song_download = pool.submit(
                                            self._download_clip, video_id, song_wav, ffmpeg_dir
                                        )
                                        video_download = pool.submit(
                                            self._download_clip,
                                            str(counterpart_id),
                                            video_wav,
                                            ffmpeg_dir,
                                        )
                                        song_download.result()
                                        video_download.result()
                                finally:
                                    os.environ["PATH"] = old_path
                            offset, confidence = self._compute_offset(song_wav, video_wav)
                            result = {
                                "available": True,
                                "counterpartVideoId": counterpart_id,
                                "offsetSeconds": offset,
                                "confidence": confidence,
                            }
                        finally:
                            shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as error:
                self._logger.warning("[video-sync] offset failed for %s: %s", video_id, error)
                result = {"available": False, "error": str(error)}

            if "error" not in result:
                with contextlib.suppress(OSError):
                    cache_path.write_text(json.dumps(result), encoding="utf-8")
            return result

    @staticmethod
    def _video_format(max_height: int | None) -> str:
        height = f"[height<=?{int(max_height)}]" if max_height else ""
        return (
            f"bestvideo[ext=mp4]{height}/bestvideo{height}/"
            f"best[ext=mp4][acodec!=none][vcodec!=none]{height}/"
            f"best[acodec!=none][vcodec!=none]{height}"
        )

    @staticmethod
    def _stream_from_info(info: Mapping[str, object]) -> str | None:
        direct = info.get("url")
        if isinstance(direct, str) and info.get("vcodec") not in (None, "none"):
            return direct
        formats = info.get("formats")
        if not isinstance(formats, list):
            return None
        candidates = [
            entry
            for entry in formats
            if isinstance(entry, dict)
            and isinstance(entry.get("url"), str)
            and entry.get("vcodec") not in (None, "none")
        ]
        candidates.sort(key=lambda entry: entry.get("height") or 0)
        return cast("str", candidates[-1]["url"]) if candidates else None

    def _extract_video(
        self,
        video_id: str,
        video_format: str | None,
        extra: Mapping[str, object] | None,
        anonymous: bool,
        use_music_host: bool = True,
    ) -> dict[str, object]:
        import yt_dlp

        options: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        if video_format:
            options["format"] = video_format
        if extra:
            options.update(extra)
        if not anonymous:
            self._ytdlp.apply_active_session_auth(options)
        host = "music.youtube.com" if use_music_host else "www.youtube.com"
        with yt_dlp.YoutubeDL(cast("yt_dlp._Params", options)) as ydl:
            return cast(
                "dict[str, object]",
                ydl.extract_info(f"https://{host}/watch?v={video_id}", download=False),
            )

    def resolve_video_stream(
        self, video_id: str, max_height: int | None
    ) -> tuple[dict[str, object], int]:
        """Resolve a playable video-only (or progressive fallback) URL."""
        if max_height is not None and max_height <= 0:
            max_height = None
        video_format = self._video_format(max_height)
        last_error: Exception | None = None
        for _audio_format, extra, anonymous in config_ytdlp.STREAM_ATTEMPTS:
            try:
                info = self._extract_video(video_id, video_format, extra, anonymous)
                url = self._stream_from_info(info)
                if url:
                    return {"url": url}, 200
            except Exception as error:
                last_error = error
                if is_hard_error(str(error)):
                    break

        hard_stop = False
        extras = (
            None,
            config_ytdlp.WEB_MUSIC_OPTIONS,
            config_ytdlp.MWEB_OPTIONS,
            config_ytdlp.ANDROID_OPTIONS,
            config_ytdlp.IOS_OPTIONS,
            config_ytdlp.TV_OPTIONS,
        )
        for anonymous, use_music_host in ((False, True), (True, True), (True, False)):
            if hard_stop:
                break
            for extra in extras:
                if (
                    extra
                    in (
                        config_ytdlp.ANDROID_OPTIONS,
                        config_ytdlp.IOS_OPTIONS,
                        config_ytdlp.TV_OPTIONS,
                        config_ytdlp.MWEB_OPTIONS,
                    )
                    and not anonymous
                ):
                    continue
                try:
                    info = self._extract_video(video_id, None, extra, anonymous, use_music_host)
                    formats = info.get("formats")
                    if max_height and isinstance(formats, list):
                        capped = [
                            entry
                            for entry in formats
                            if isinstance(entry, dict) and (entry.get("height") or 0) <= max_height
                        ]
                        if capped:
                            info = {**info, "formats": capped}
                    url = self._stream_from_info(info)
                    if url:
                        return {"url": url}, 200
                except Exception as error:
                    last_error = error
                    if is_hard_error(str(error)) or is_unavailable(str(error)):
                        hard_stop = True
                        break

        message = str(last_error) if last_error else "No playable video URL found"
        self._logger.error("[video-sync] stream failed for %s: %s", video_id, message)
        return {"error": message}, 500
