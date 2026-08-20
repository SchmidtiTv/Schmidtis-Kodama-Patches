"""A per-key mutual-exclusion lock.

Some operations are expensive enough that concurrent duplicate calls for the
*same* key should serialize (so N callers don't kick off N redundant expensive
jobs — e.g. N concurrent yt-dlp extractions for one video), while calls for
*different* keys must run fully independently. A single shared ``Lock``
serializes everything, including unrelated keys; ``KeyedLock`` only serializes
callers holding the same key, and drops each entry once nobody is waiting on
it so the lock table cannot grow without bound over a long session.
"""

import threading
from contextlib import contextmanager
from typing import Hashable, Iterator


class _Entry:
    __slots__ = ("lock", "refs")

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.refs = 0


class KeyedLock:
    def __init__(self) -> None:
        self._table_guard = threading.Lock()
        self._entries: dict[Hashable, _Entry] = {}

    @contextmanager
    def acquire(self, key: Hashable) -> Iterator[None]:
        """Hold the lock for ``key`` for the duration of the ``with`` block."""
        entry = self._checkout(key)
        try:
            with entry.lock:
                yield
        finally:
            self._checkin(key, entry)

    def _checkout(self, key: Hashable) -> _Entry:
        with self._table_guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _Entry()
                self._entries[key] = entry
            entry.refs += 1
            return entry

    def _checkin(self, key: Hashable, entry: _Entry) -> None:
        with self._table_guard:
            entry.refs -= 1
            # Only the last holder removes the entry, and only if nobody else has
            # already replaced it in the table (a new caller may have raced in
            # right after refs hit 0 and before this lock was reacquired).
            if entry.refs == 0 and self._entries.get(key) is entry:
                del self._entries[key]
