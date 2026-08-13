"""In-memory and SQLite-backed playlist cache.

The in-memory layer is an LRU keyed by playlist id; the persistent layer is
profile-scoped so account-relative playlist ids never collide.
"""

import collections
import contextlib
import json
import os
import sqlite3
import time
from typing import cast

from src.config import Config, config_dirs, config_ytmusic
from src.lib.runtime.metadata_cache import MetadataCache


class Playlist:
    # Old server.py: _playlist_cache
    def __init__(self, metadata_cache: MetadataCache | None = None) -> None:
        # Keyed by (profile, playlist_id): account-relative ids such as "LM"
        # (Liked Songs) are shared across Google accounts but hold different
        # content, so the in-memory layer must be profile-scoped just like the
        # on-disk layer. LRU eviction is over the whole map.
        self.playlist_cache: collections.OrderedDict[tuple[str, str], dict[str, object]] = (
            collections.OrderedDict()
        )
        self._metadata_cache = metadata_cache or MetadataCache(config_dirs.CACHE_DATABASE)

    @staticmethod
    def _memory_key(playlist_id: str, profile: str | None) -> tuple[str, str]:
        return (profile or "default", playlist_id)

    # Old server.py: _playlist_disk_path
    def playlist_disk_path(self, playlist_id: str, profile: str | None) -> str:
        prefix = profile or "default"
        safe = playlist_id.replace("/", "_").replace("\\", "_")
        return os.path.join(config_dirs.PLAYLIST_CACHE_DIR, f"{prefix}_{safe}.json")

    @staticmethod
    def _disk_key(playlist_id: str, profile: str | None) -> str:
        return f"{profile or 'default'}:{playlist_id}"

    # Old server.py: _load_playlist_disk
    def load_playlist_disk(
        self, playlist_id: str, profile: str | None, ttl: int = Config.PLAYLIST_CACHE_TTL
    ) -> dict[str, object] | None:
        key = self._disk_key(playlist_id, profile)
        try:
            data = self._metadata_cache.get("playlists", key, ttl)
        except (OSError, sqlite3.Error):
            data = None
        if data is not None:
            tracks = cast("list[dict[str, object]]", data.get("tracks", []))
            return None if tracks and "isExplicit" not in tracks[0] else data

        # Import pre-SQLite caches lazily, preserving existing installations.
        path = self.playlist_disk_path(playlist_id, profile)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > ttl:
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = cast("dict[str, object]", json.load(f))
            # Invalidate old caches that don't have isExplicit yet
            tracks = cast("list[dict[str, object]]", data.get("tracks", []))
            if tracks and "isExplicit" not in tracks[0]:
                return None
            self._metadata_cache.put("playlists", key, data)
            with contextlib.suppress(OSError):
                os.remove(path)
            return data
        except (OSError, ValueError, TypeError):
            return None

    # Old server.py: _save_playlist_disk
    def save_playlist_disk(
        self, playlist_id: str, profile: str | None, data: dict[str, object]
    ) -> None:
        with contextlib.suppress(OSError, sqlite3.Error, TypeError, ValueError):
            self._metadata_cache.put("playlists", self._disk_key(playlist_id, profile), data)

    # Old server.py: _purge_playlist_cache
    def purge_playlist_cache(self, playlist_id: str, profile: str | None) -> None:
        self.discard_memory(playlist_id, profile)
        with contextlib.suppress(OSError, sqlite3.Error):
            self._metadata_cache.delete("playlists", self._disk_key(playlist_id, profile))
        path = self.playlist_disk_path(playlist_id, profile)
        if os.path.exists(path):
            os.remove(path)

    def get_memory(self, playlist_id: str, profile: str | None) -> dict[str, object] | None:
        """Return the in-memory cached entry for this profile, or None."""
        return self.playlist_cache.get(self._memory_key(playlist_id, profile))

    def discard_memory(self, playlist_id: str, profile: str | None) -> None:
        """Drop a single in-memory entry (e.g. when it is stale)."""
        self.playlist_cache.pop(self._memory_key(playlist_id, profile), None)

    def clear_memory(self) -> None:
        """Drop every in-memory entry (used by the 'clear caches' action)."""
        self.playlist_cache.clear()

    def clear_memory_for_profile(self, profile: str | None) -> None:
        """Drop in-memory playlists belonging to one profile only."""
        profile_key = profile or "default"
        for key in [key for key in self.playlist_cache if key[0] == profile_key]:
            self.playlist_cache.pop(key, None)

    # Old server.py: _playlist_cache_put
    def put(self, playlist_id: str, profile: str | None, data: dict[str, object]) -> None:
        """Insert/update a playlist and evict the least-recently-used entry."""
        key = self._memory_key(playlist_id, profile)
        self.playlist_cache[key] = data
        self.playlist_cache.move_to_end(key)
        while len(self.playlist_cache) > config_ytmusic.PLAYLIST_CACHE_MAX:
            self.playlist_cache.popitem(last=False)
