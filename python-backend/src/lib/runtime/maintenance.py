"""Small process-maintenance helpers."""

import heapq
import os
import threading
import time
from collections.abc import MutableMapping
from os import PathLike
from typing import TypeVar


Key = TypeVar("Key")
Value = TypeVar("Value")


class DelayedCleanup:
    """Schedules temporary entries with one shared daemon worker."""

    _condition = threading.Condition()
    _entries: list[tuple[float, int, MutableMapping[object, object], object]] = []
    _latest_tokens: dict[tuple[int, object], int] = {}
    _next_token = 0
    _worker_started = False

    # Old server.py: _schedule_cleanup
    @classmethod
    def schedule_removal(cls, data: MutableMapping[Key, Value], key: Key, delay: float = 300) -> None:
        """Remove *key* from *data* after *delay* seconds."""
        with cls._condition:
            cls._next_token += 1
            token = cls._next_token
            entry_key = (id(data), key)
            cls._latest_tokens[entry_key] = token
            heapq.heappush(cls._entries, (time.monotonic() + delay, token, data, key))
            if not cls._worker_started:
                threading.Thread(target=cls._run, daemon=True, name="delayed-cleanup").start()
                cls._worker_started = True
            cls._condition.notify()

    @classmethod
    def cancel_removal(cls, data: MutableMapping[Key, Value], key: Key) -> None:
        """Keep a newly reused entry from being removed by an older schedule."""
        with cls._condition:
            cls._latest_tokens.pop((id(data), key), None)

    @classmethod
    def _run(cls) -> None:
        while True:
            with cls._condition:
                while not cls._entries:
                    cls._condition.wait()
                deadline, token, data, key = cls._entries[0]
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    cls._condition.wait(timeout=remaining)
                    continue
                heapq.heappop(cls._entries)
                entry_key = (id(data), key)
                if cls._latest_tokens.get(entry_key) != token:
                    continue
                del cls._latest_tokens[entry_key]
            data.pop(key, None)


class DirectoryInspector:
    """Calculates basic storage usage for a single directory."""

    @staticmethod
    # Old server.py: _dir_size_and_count
    def size_and_file_count(path: str | PathLike[str]) -> tuple[int, int]:
        """Return ``(total_bytes, file_count)`` for direct child files."""
        total, count = 0, 0
        try:
            for filename in os.listdir(path):
                file_path = os.path.join(path, filename)
                if os.path.isfile(file_path):
                    total += os.path.getsize(file_path)
                    count += 1
        except OSError:
            pass
        return total, count
