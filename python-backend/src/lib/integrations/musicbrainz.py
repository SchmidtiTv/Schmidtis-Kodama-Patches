"""Rate-limited JSON client for the MusicBrainz web service."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
import time
from typing import Any

import requests

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2"
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Kodama/1.0 (+https://github.com/KiyoshiTheDevil/Kodama)",
}
REQUEST_TIMEOUT = (2, 4)
MIN_REQUEST_INTERVAL = 1.0


class MusicBrainzError(Exception):
    """Raised when a MusicBrainz request cannot be completed."""


class MusicBrainz:
    """Thin, rate-limited wrapper around the MusicBrainz web service.

    MusicBrainz asks that unauthenticated clients stay at or below one
    request per second, so every call is serialized behind a lock that
    waits out the remainder of that window.
    """

    def __init__(
        self,
        get: Callable[..., requests.Response] = requests.get,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        min_request_interval: float = MIN_REQUEST_INTERVAL,
    ) -> None:
        self._get = get
        self._monotonic = monotonic
        self._sleep = sleep
        self._min_request_interval = min_request_interval
        self._lock = Lock()
        self._last_request = 0.0

    def search_artists(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search artists with a Lucene ``query`` string."""
        payload = self._get_json(
            f"{MUSICBRAINZ_URL}/artist/", {"query": query, "fmt": "json", "limit": limit}
        )
        artists = payload.get("artists", [])
        return artists if isinstance(artists, list) else []

    def search_releases(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search releases (album editions) with a Lucene ``query`` string.

        Results are ranked by MusicBrainz's own ``score`` field (0-100).
        """
        payload = self._get_json(
            f"{MUSICBRAINZ_URL}/release/", {"query": query, "fmt": "json", "limit": limit}
        )
        releases = payload.get("releases", [])
        return releases if isinstance(releases, list) else []

    def get_artist(self, artist_id: str, inc: str) -> dict[str, Any]:
        """Fetch an artist by id, including the relations named by ``inc``."""
        return self._get_json(f"{MUSICBRAINZ_URL}/artist/{artist_id}", {"inc": inc, "fmt": "json"})

    def get_release(
        self, release_id: str, inc: str = "recordings+artist-credits+labels"
    ) -> dict[str, Any]:
        """Fetch a release (album edition) by id, including the data named by ``inc``.

        The default ``inc`` returns the tracklist (``media[*].tracks``), the
        performing artist(s) (``artist-credit``), and label/catalog info
        (``label-info``).
        """
        return self._get_json(
            f"{MUSICBRAINZ_URL}/release/{release_id}", {"inc": inc, "fmt": "json"}
        )

    def _get_json(self, url: str, params: dict[str, object]) -> dict[str, Any]:
        self._wait_for_rate_limit()
        try:
            response = self._get(
                url, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, AttributeError) as error:
            raise MusicBrainzError from error
        if not isinstance(payload, dict):
            raise MusicBrainzError
        return payload

    def _wait_for_rate_limit(self) -> None:
        with self._lock:
            wait_seconds = self._min_request_interval - (self._monotonic() - self._last_request)
            if wait_seconds > 0:
                self._sleep(wait_seconds)
            self._last_request = self._monotonic()
