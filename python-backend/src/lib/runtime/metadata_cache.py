"""SQLite-backed storage for structured cache entries.

Cache values remain JSON-serializable, but SQLite provides indexed lookups,
atomic writes, and cheap category-wide statistics without creating thousands
of small files.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import cast


class MetadataCache:
    """Store JSON-compatible cache values in one small SQLite database."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # One connection per thread, opened once and reused for that thread's lifetime, instead
        # of a fresh connect() + two PRAGMAs on every call. This cache is read on the hottest
        # path in the app (every video-variant track in every playlist/home/liked-songs load), so
        # a 200-track load previously meant 200+ fresh connections; now it's one per request
        # thread. A single shared connection isn't an option — SQLite connections may only be
        # used from the thread that created them.
        self._local = threading.local()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = sqlite3.connect(self.path, timeout=5)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection = connection
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    category TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    payload_bytes INTEGER NOT NULL,
                    PRIMARY KEY (category, cache_key)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS cache_entries_updated_at "
                "ON cache_entries(category, updated_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_counterparts (
                    video_id TEXT PRIMARY KEY,
                    audio_payload TEXT NOT NULL,
                    resolved_at REAL NOT NULL,
                    payload_bytes INTEGER NOT NULL
                )
                """
            )

    def get(self, category: str, key: str, ttl: int | None = None) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload, updated_at FROM cache_entries WHERE category = ? AND cache_key = ?",
                (category, key),
            ).fetchone()
        if row is None:
            return None
        if ttl is not None and time.time() - float(row[1]) > ttl:
            self.delete(category, key)
            return None
        try:
            value = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            self.delete(category, key)
            return None
        return cast(dict[str, object], value) if isinstance(value, dict) else None

    def put(self, category: str, key: str, value: dict[str, object]) -> None:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries(category, cache_key, payload, updated_at, payload_bytes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(category, cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at,
                    payload_bytes = excluded.payload_bytes
                """,
                (category, key, payload, time.time(), len(payload.encode("utf-8"))),
            )

    def move_categories_to(self, destination: "MetadataCache", categories: tuple[str, ...]) -> None:
        """Move selected categories to another database without replacing newer values."""
        if self.path.resolve() == destination.path.resolve() or not categories:
            return
        placeholders = ",".join("?" for _ in categories)
        with self._connect() as source:
            rows = source.execute(
                f"""
                SELECT category, cache_key, payload, updated_at, payload_bytes
                FROM cache_entries
                WHERE category IN ({placeholders})
                """,
                categories,
            ).fetchall()
        if not rows:
            return
        with destination._connect() as target:
            target.executemany(
                """
                INSERT INTO cache_entries(category, cache_key, payload, updated_at, payload_bytes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(category, cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at,
                    payload_bytes = excluded.payload_bytes
                WHERE excluded.updated_at > cache_entries.updated_at
                """,
                rows,
            )
        with self._connect() as source:
            source.execute(
                f"DELETE FROM cache_entries WHERE category IN ({placeholders})",
                categories,
            )

    def delete(self, category: str, key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM cache_entries WHERE category = ? AND cache_key = ?",
                (category, key),
            )

    def clear(self, category: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM cache_entries WHERE category = ?", (category,))

    def stats(self, category: str) -> tuple[int, int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(payload_bytes), 0), COUNT(*) FROM cache_entries WHERE category = ?",
                (category,),
            ).fetchone()
        return (int(row[0]), int(row[1])) if row else (0, 0)

    def get_audio_counterpart(
        self, video_id: str, ttl: int | None = None
    ) -> dict[str, object] | None:
        """Return the resolved audio track stored for one video id."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT audio_payload, resolved_at FROM audio_counterparts WHERE video_id = ?",
                (video_id,),
            ).fetchone()
        if row is None:
            return None
        if ttl is not None and time.time() - float(row[1]) > ttl:
            self.delete_audio_counterpart(video_id)
            return None
        try:
            value = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            self.delete_audio_counterpart(video_id)
            return None
        return cast(dict[str, object], value) if isinstance(value, dict) else None

    def put_audio_counterpart(self, video_id: str, audio_track: dict[str, object]) -> None:
        """Atomically insert or refresh a video-to-audio resolution."""
        payload = json.dumps(audio_track, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audio_counterparts(video_id, audio_payload, resolved_at, payload_bytes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    audio_payload = excluded.audio_payload,
                    resolved_at = excluded.resolved_at,
                    payload_bytes = excluded.payload_bytes
                """,
                (video_id, payload, time.time(), len(payload.encode("utf-8"))),
            )

    def delete_audio_counterpart(self, video_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM audio_counterparts WHERE video_id = ?", (video_id,))

    def clear_audio_counterparts(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM audio_counterparts")

    def audio_counterpart_stats(self) -> tuple[int, int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(payload_bytes), 0), COUNT(*) FROM audio_counterparts"
            ).fetchone()
        return (int(row[0]), int(row[1])) if row else (0, 0)
