"""Cached application service for normalized song credits."""

import re
from collections import OrderedDict

from src.lib.providers.contracts import SongCreditsProvider
from src.lib.providers.models import SongCredits


class SongCreditsCache:
    def __init__(self, max_entries: int = 100) -> None:
        self._entries: OrderedDict[str, SongCredits] = OrderedDict()
        self._max_entries = max_entries

    def get(self, video_id: str) -> SongCredits | None:
        entry = self._entries.get(video_id)
        if entry is not None:
            self._entries.move_to_end(video_id)
        return entry

    def put(self, video_id: str, credits: SongCredits) -> None:
        self._entries[video_id] = credits
        self._entries.move_to_end(video_id)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


class SongCreditsService:
    _VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

    def __init__(self, provider: SongCreditsProvider, cache: SongCreditsCache) -> None:
        self._provider = provider
        self._cache = cache

    def get_credits(self, video_id: str) -> SongCredits:
        if not self._VIDEO_ID.fullmatch(video_id):
            raise ValueError("Invalid video ID")
        cached = self._cache.get(video_id)
        if cached is not None:
            return cached
        credits = self._provider.get_credits(video_id)
        self._cache.put(video_id, credits)
        return credits
