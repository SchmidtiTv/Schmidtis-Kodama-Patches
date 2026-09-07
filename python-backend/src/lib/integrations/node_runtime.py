"""Discover, preserve, and repair the Node.js runtime used by yt-dlp."""

import hashlib
import logging
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import threading
from pathlib import Path

import requests

from src.config import ConfigYTDLP


class NodeRuntime:
    """Makes a bundled Node executable survive slim app updates when possible."""

    def __init__(
        self,
        runtime_dir: Path,
        logger: logging.Logger | None = None,
        bundle_roots: list[Path] | None = None,
    ) -> None:
        self.runtime_dir = runtime_dir
        self.logger = logger or logging.getLogger(__name__)
        self.bundle_roots = bundle_roots or self._default_bundle_roots()
        self._prepare_started = False
        self._lock = threading.Lock()

    @property
    def executable_name(self) -> str:
        return "node.exe" if sys.platform == "win32" else "node"

    @property
    def installed_path(self) -> Path:
        return self.runtime_dir / self.executable_name

    def ensure_in_path(self) -> None:
        """Expose a usable Node now and repair the persistent copy in the background."""
        node = self._find_node()
        if node:
            self._prepend_to_path(node.parent)
            self._start_prepare()
            return

        self.logger.warning("[runtime] Node.js is unavailable; yt-dlp decryption may be limited")
        self._start_prepare()

    def _default_bundle_roots(self) -> list[Path]:
        executable_dir = Path(sys.executable).resolve().parent
        parent_dir = executable_dir.parent
        roots = [executable_dir, parent_dir]
        if sys.platform == "darwin":
            roots.extend((parent_dir / "Resources", executable_dir / ".." / "Resources"))
        return roots

    def _find_node(self) -> Path | None:
        override = os.environ.get("KODAMA_NODE")
        candidates = [Path(override)] if override else []
        candidates.append(self.installed_path)
        candidates.extend(root / self.executable_name for root in self.bundle_roots)
        path_node = shutil.which("node")
        if path_node:
            candidates.append(Path(path_node))
        return next((path for path in candidates if path.is_file()), None)

    def _prepend_to_path(self, directory: Path) -> None:
        location = str(directory)
        paths = os.environ.get("PATH", "").split(os.pathsep)
        if location not in paths:
            os.environ["PATH"] = location + os.pathsep + os.environ.get("PATH", "")

    def _start_prepare(self) -> None:
        with self._lock:
            if self._prepare_started:
                return
            self._prepare_started = True
        threading.Thread(target=self._prepare, name="node-runtime-prepare", daemon=True).start()

    def _prepare(self) -> None:
        if not self.installed_path.is_file():
            bundled = next(
                (
                    root / self.executable_name
                    for root in self.bundle_roots
                    if (root / self.executable_name).is_file()
                ),
                None,
            )
            if bundled:
                self._adopt(bundled)
            else:
                self._download()
        if self.installed_path.is_file():
            self._prepend_to_path(self.runtime_dir)

    def _adopt(self, source: Path) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.installed_path.with_suffix(self.installed_path.suffix + ".incoming")
        try:
            shutil.copy2(source, temporary)
            temporary.chmod(0o755)
            temporary.replace(self.installed_path)
            self.logger.info("[runtime] adopted bundled Node.js runtime")
        except OSError as error:
            temporary.unlink(missing_ok=True)
            self.logger.warning("[runtime] could not preserve bundled Node.js: %s", error)

    def _download_spec(self) -> tuple[str, str, str] | None:
        if sys.platform == "win32":
            return (
                f"https://nodejs.org/dist/{ConfigYTDLP.NODE_VERSION}/win-x64/node.exe",
                "exe",
                "win-x64/node.exe",
            )
        if sys.platform == "darwin":
            arch = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"
            filename = f"node-{ConfigYTDLP.NODE_VERSION}-darwin-{arch}.tar.gz"
            return (
                f"https://nodejs.org/dist/{ConfigYTDLP.NODE_VERSION}/{filename}",
                "tar",
                filename,
            )
        return None

    def _expected_checksum(self, filename: str) -> str | None:
        try:
            response = requests.get(
                f"https://nodejs.org/dist/{ConfigYTDLP.NODE_VERSION}/SHASUMS256.txt", timeout=20
            )
            response.raise_for_status()
        except requests.RequestException as error:
            self.logger.warning("[runtime] could not fetch Node.js checksums: %s", error)
            return None
        for line in response.text.splitlines():
            digest, separator, name = line.partition("  ")
            if separator and name.strip() == filename:
                return digest.strip()
        return None

    def _download(self) -> None:
        spec = self._download_spec()
        if spec is None:
            return
        url, kind, filename = spec
        checksum = self._expected_checksum(filename)
        if not checksum:
            self.logger.warning("[runtime] Node.js checksum missing; download skipped")
            return
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.runtime_dir, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                digest = hashlib.sha256()
                with requests.get(url, stream=True, timeout=120) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(1 << 20):
                        if chunk:
                            digest.update(chunk)
                            temporary.write(chunk)
            if digest.hexdigest() != checksum:
                self.logger.error("[runtime] Node.js checksum mismatch; download discarded")
                return
            if kind == "tar":
                with tarfile.open(temporary_path) as archive:
                    member = next(
                        (
                            entry
                            for entry in archive.getmembers()
                            if entry.name.endswith("/bin/node")
                        ),
                        None,
                    )
                    if member is None or not member.isfile():
                        self.logger.error("[runtime] downloaded Node.js archive has no executable")
                        return
                    source = archive.extractfile(member)
                    if source is None:
                        return
                    extracted = self.installed_path.with_suffix(".incoming")
                    with source, extracted.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
                temporary_path.unlink(missing_ok=True)
                temporary_path = extracted
            temporary_path.chmod(0o755)
            temporary_path.replace(self.installed_path)
            temporary_path = None
            self.logger.info("[runtime] downloaded Node.js runtime")
        except (OSError, requests.RequestException, tarfile.TarError) as error:
            self.logger.warning("[runtime] Node.js download failed: %s", error)
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)
