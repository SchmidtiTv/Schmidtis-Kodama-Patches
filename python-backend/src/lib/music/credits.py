"""Bounded cache for song descriptions and credits scraped from YouTube."""

from collections import OrderedDict


class SongCreditsCache:
    """Keep recent credits payloads without route-module-level mutable state."""

    def __init__(self, max_entries: int = 100) -> None:
        self._entries: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._max_entries = max_entries

    def get(self, video_id: str) -> dict[str, object] | None:
        entry = self._entries.get(video_id)
        if entry is not None:
            self._entries.move_to_end(video_id)
        return entry

    def put(self, video_id: str, payload: dict[str, object]) -> None:
        self._entries[video_id] = payload
        self._entries.move_to_end(video_id)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()
