"""FFmpeg discovery, version checks, and managed auto-downloads."""

import json
import os
import platform
import sys
import time
from collections.abc import Generator
from typing import Optional, TypedDict

import requests

from src.config import PROJECT_ROOT, config_dirs


FFMPEG_MAC_REPOSITORY = "eugeneware/ffmpeg-static"
MIN_FFMPEG_DOWNLOAD_BYTES = 1_000_000
# Sentinel distinguishing "not yet resolved" from find()'s legitimate `None` return (found on
# PATH), since `str | None | bool` already uses every other value.
_UNRESOLVED = object()


class LatestVersion(TypedDict):
    ts: float
    ver: Optional[str]


class FFmpeg:
    """Locate ffmpeg and fetch a managed binary on Windows or macOS."""

    def __init__(self) -> None:
        # Old server.py: _FFMPEG_LATEST
        self._latest: LatestVersion = {"ts": 0.0, "ver": None}
        self._cached_find: str | None | bool = _UNRESOLVED

    # Old server.py: _find_ffmpeg
    def find(self) -> str | None | bool:
        """Return the directory holding ffmpeg, ``None`` if it is on PATH, or
        ``False`` if it cannot be found.

        This rescans a handful of filesystem candidates plus (on a PATH miss) shells out to
        ``shutil.which`` — called per-track by mix analysis and video-sync, so a successful
        resolution is cached: ffmpeg's location can't move once found. A miss is never cached,
        so this keeps re-scanning after an auto-install (``download_stream``) places the binary.
        """
        if self._cached_find is not _UNRESOLVED:
            return self._cached_find
        result = self._locate()
        if result is not False:
            self._cached_find = result
        return result

    def _locate(self) -> str | None | bool:
        bin_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        candidates = []
        if sys.platform != "win32":
            candidates.append(str(config_dirs.BIN_DIR / bin_name))
        if getattr(sys, "frozen", False):
            # Next to the server executable (primary install-dir location)
            candidates.append(os.path.join(os.path.dirname(sys.executable), bin_name))
            # PyInstaller _MEIPASS temp dir (in case user bundled ffmpeg inside)
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(os.path.join(meipass, bin_name))
                # One level up from _MEIPASS (install dir)
                candidates.append(os.path.join(os.path.dirname(meipass), bin_name))
        else:
            candidates.append(os.path.join(str(PROJECT_ROOT), bin_name))

        # macOS: also probe the app bundle's Resources and the common Homebrew
        # locations (existing Homebrew installations remain a supported fallback).
        if sys.platform == "darwin":
            if getattr(sys, "frozen", False):
                candidates.append(os.path.join(os.path.dirname(sys.executable), "..", "Resources", bin_name))
            candidates.append("/opt/homebrew/bin/ffmpeg")   # Apple Silicon brew
            candidates.append("/usr/local/bin/ffmpeg")       # Intel brew

        for bundled in candidates:
            if os.path.exists(bundled):
                return os.path.dirname(bundled)

        # Check PATH
        import shutil
        if shutil.which("ffmpeg"):
            return None  # yt-dlp will find it in PATH
        return False  # not found

    # Old server.py: _ffmpeg_exe_path
    def exe_path(self) -> Optional[str]:
        """Absolute path (or bare 'ffmpeg' for PATH) to the binary, or None if unavailable."""
        directory = self.find()
        if directory is False:
            return None
        bin_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        return os.path.join(directory, bin_name) if isinstance(directory, str) else bin_name

    def available(self) -> bool:
        return self.find() is not False

    # Old server.py: _ffmpeg_version
    def version(self) -> Optional[str]:
        """Installed ffmpeg version as a dotted string (e.g. '8.1'), or None."""
        import re
        import subprocess
        exe = self.exe_path()
        if not exe:
            return None
        try:
            out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=10).stdout or ""
            m = re.search(r"version\s+(\d+(?:\.\d+)+)", out)
            return m.group(1) if m else None
        except Exception:
            return None

    # Old server.py: _ffmpeg_latest_version
    def latest_version(self) -> Optional[str]:
        """Latest version from the platform's download source, cached for one hour."""
        now = time.time()
        if self._latest["ver"] and now - self._latest["ts"] < 3600:
            return self._latest["ver"]
        try:
            if sys.platform == "darwin":
                response = requests.get(
                    f"https://api.github.com/repos/{FFMPEG_MAC_REPOSITORY}/releases/latest",
                    headers={"Accept": "application/vnd.github+json"},
                    timeout=10,
                )
                response.raise_for_status()
                ver = (response.json().get("tag_name") or "").lstrip("bv").strip()
            else:
                response = requests.get(
                    "https://www.gyan.dev/ffmpeg/builds/release-version",
                    timeout=10,
                )
                response.raise_for_status()
                ver = (response.text or "").strip()
            if ver:
                self._latest.update(ts=now, ver=ver)
                return ver
        except Exception:
            pass
        return None

    @staticmethod
    # Old server.py: _ver_tuple
    def version_tuple(v: str) -> tuple[int, ...]:
        import re
        return tuple(int(x) for x in re.findall(r"\d+", v or ""))

    # Old server.py: ffmpeg_check_update
    def check_update(self) -> dict[str, object]:
        installed = self.version()
        latest = self.latest_version()
        update = bool(installed and latest and self.version_tuple(latest) > self.version_tuple(installed))
        return {"installed": installed, "latest": latest, "updateAvailable": update}

    @staticmethod
    def mac_asset_name() -> str:
        architecture = "arm64" if platform.machine() == "arm64" else "x64"
        return f"ffmpeg-darwin-{architecture}"

    @classmethod
    def mac_download_url(cls) -> str:
        return (
            f"https://github.com/{FFMPEG_MAC_REPOSITORY}/releases/latest/download/"
            f"{cls.mac_asset_name()}"
        )

    @staticmethod
    def _progress_payload(downloaded: int, total: int, started_at: float) -> str:
        elapsed = max(time.time() - started_at, 0.001)
        return json.dumps({
            "status": "progress",
            "percent": int(downloaded / total * 100) if total else 0,
            "mb_done": round(downloaded / 1048576, 1),
            "mb_total": round(total / 1048576, 1) if total else 0,
            "speed_kbps": int(downloaded / elapsed / 1024),
        })

    def _download_macos(self, force: bool) -> Generator[str, None, None]:
        destination = config_dirs.BIN_DIR / "ffmpeg"
        if destination.exists() and not force:
            yield 'data: {"status": "done"}\n\n'
            return

        temporary = destination.with_name(f"{destination.name}.new")
        try:
            config_dirs.BIN_DIR.mkdir(parents=True, exist_ok=True)
            with requests.get(
                self.mac_download_url(),
                stream=True,
                timeout=30,
                allow_redirects=True,
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                downloaded = 0
                started_at = time.time()
                last_emit = 0.0
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        output.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if now - last_emit >= 0.25:
                            yield f"data: {self._progress_payload(downloaded, total, started_at)}\n\n"
                            last_emit = now

            if downloaded < MIN_FFMPEG_DOWNLOAD_BYTES:
                temporary.unlink(missing_ok=True)
                yield "data: " + json.dumps({
                    "status": "error",
                    "message": "Download unvollständig — bitte erneut versuchen.",
                }) + "\n\n"
                return

            temporary.chmod(0o755)
            os.replace(temporary, destination)
            yield 'data: {"status": "done"}\n\n'
        except Exception as error:
            temporary.unlink(missing_ok=True)
            yield f"data: {json.dumps({'status': 'error', 'message': str(error)})}\n\n"

    # Old server.py: ffmpeg_download (_stream generator)
    def download_stream(self, force: bool = False) -> Generator[str, None, None]:
        """Yield SSE events while installing ffmpeg from the platform source."""
        import io
        import zipfile

        if sys.platform == "darwin":
            yield from self._download_macos(force)
            return
        # Only runs when frozen (installed); in dev just report done.
        if not getattr(sys, "frozen", False):
            yield "data: {\"status\": \"done\"}\n\n"
            return

        dest_dir = os.path.dirname(sys.executable)
        dest_exe = os.path.join(dest_dir, "ffmpeg.exe")

        if os.path.exists(dest_exe) and not force:
            yield "data: {\"status\": \"done\"}\n\n"
            return

        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        try:
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                chunks = []
                start_ts = time.time()
                last_emit = 0

                for chunk in r.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_emit >= 0.25:
                        payload = self._progress_payload(downloaded, total, start_ts)
                        yield f"data: {payload}\n\n"
                        last_emit = now

                # Extract ffmpeg.exe from ZIP
                zip_data = b"".join(chunks)
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                    ffmpeg_entry = next(
                        (n for n in zf.namelist()
                         if n.endswith("/ffmpeg.exe") or n == "ffmpeg.exe"),
                        None
                    )
                    if not ffmpeg_entry:
                        yield "data: {\"status\": \"error\", \"message\": \"ffmpeg.exe not found in ZIP\"}\n\n"
                        return
                    # Write to a temp file then atomically replace, so an update overwrites
                    # the existing binary cleanly (and a failed write can't corrupt it).
                    tmp_exe = dest_exe + ".new"
                    with zf.open(ffmpeg_entry) as src, open(tmp_exe, "wb") as dst:
                        dst.write(src.read())
                    os.replace(tmp_exe, dest_exe)

                yield "data: {\"status\": \"done\"}\n\n"

        except Exception as e:
            payload = json.dumps({"status": "error", "message": str(e)})
            yield f"data: {payload}\n\n"
