"""SQLite-backed album cache. Albums are global and keyed by browse id."""

import contextlib
import json
import os
import sqlite3
import time
from typing import cast

from src.config import Config, config_dirs
from src.lib.runtime.metadata_cache import MetadataCache


class Album:
    def __init__(self, metadata_cache: MetadataCache | None = None) -> None:
        self._metadata_cache = metadata_cache or MetadataCache(config_dirs.CACHE_DATABASE)

    # Old server.py: _album_disk_path
    def album_disk_path(self, browse_id: str) -> str:
        safe = browse_id.replace("/", "_").replace("\\", "_")
        return os.path.join(config_dirs.ALBUM_CACHE_DIR, f"{safe}.json")

    # Old server.py: _load_album_disk
    def load_album_disk(self, browse_id: str) -> dict[str, object] | None:
        try:
            data = self._metadata_cache.get("albums", browse_id, Config.ALBUM_CACHE_TTL)
        except (OSError, sqlite3.Error):
            data = None
        if data is not None:
            tracks = cast("list[dict[str, object]]", data.get("tracks", []))
            return None if tracks and "isExplicit" not in tracks[0] else data

        path = self.album_disk_path(browse_id)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > Config.ALBUM_CACHE_TTL:
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = cast("dict[str, object]", json.load(f))
            # Invalidate old caches that don't have isExplicit yet
            tracks = cast("list[dict[str, object]]", data.get("tracks", []))
            if tracks and "isExplicit" not in tracks[0]:
                return None
            self._metadata_cache.put("albums", browse_id, data)
            with contextlib.suppress(OSError):
                os.remove(path)
            return data
        except (OSError, ValueError, TypeError):
            return None

    # Old server.py: _save_album_disk
    def save_album_disk(self, browse_id: str, data: dict[str, object]) -> None:
        with contextlib.suppress(OSError, sqlite3.Error, TypeError, ValueError):
            self._metadata_cache.put("albums", browse_id, data)
