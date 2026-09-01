"""Resolve short looping cover videos from public and web-player artwork sources."""

from __future__ import annotations

import base64
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import locale
import re
from threading import Lock
import time
from typing import Any
import unicodedata
from urllib.parse import urljoin

import requests

APPLE_BROWSE_URL = "https://music.apple.com/us/browse"
APPLE_API_ROOT = "https://amp-api.music.apple.com/v1/catalog"
APPLE_ORIGIN = "https://music.apple.com"
TIDAL_API_URL = "https://api.tidal.com/v1/search"
VIVI_MANIFEST_URL = "https://vivimusicanvas.mkmdevilmi.workers.dev/canvas.json"
TIDAL_TOKEN = "vNVdglQOjFJJGG2U"
REQUEST_TIMEOUT = (2, 8)
RESULT_CACHE_TTL = 24 * 60 * 60
MANIFEST_CACHE_TTL = 60
MAX_RESULT_CACHE_ENTRIES = 256
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TOKEN_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
BUNDLE_PATTERN = re.compile(r"[\"'](/assets/index(?:-legacy)?[~-][^\"']+?\.js)[\"']")


@dataclass(frozen=True)
class CanvasArtwork:
    """The remote looping artwork selected for a track."""

    source: str
    url: str


@dataclass(frozen=True)
class CanvasQuery:
    """Validated track metadata needed by external artwork sources."""

    title: str
    artist: str
    album: str
    duration_seconds: int | None
    source: str = "auto"

    @property
    def cache_key(self) -> str:
        duration = str(self.duration_seconds or 0)
        return "\x1f".join(
            (
                _normalize(self.title),
                _normalize(self.artist),
                _normalize(self.album),
                duration,
                self.source,
            )
        )


class CanvasArtworkFinder:
    """Find canvas artwork with bounded in-memory caches and graceful provider fallback."""

    def __init__(
        self,
        get: Callable[..., requests.Response] = requests.get,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._get = get
        self._now = now
        self._result_cache: OrderedDict[str, tuple[float, CanvasArtwork | None]] = OrderedDict()
        self._manifest: list[dict[str, object]] | None = None
        self._manifest_expires = 0.0
        self._apple_token: str | None = None
        self._apple_token_expires = 0.0
        self._lock = Lock()

    def find(self, query: CanvasQuery) -> CanvasArtwork | None:
        """Return the best available looping artwork without exposing provider failures."""
        cache_key = query.cache_key
        has_cached_result, cached = self._read_cached_result(cache_key)
        if has_cached_result:
            return cached

        artwork = None
        for provider in self._providers_for(query.source):
            artwork = provider(query)
            if artwork:
                break
        self._cache_result(cache_key, artwork)
        return artwork

    def _providers_for(
        self, source: str
    ) -> tuple[Callable[[CanvasQuery], CanvasArtwork | None], ...]:
        providers = {
            "apple_music": (self._find_apple_music,),
            "tidal": (self._find_tidal,),
            "vivimusic": (self._find_vivimusic,),
        }
        return providers.get(
            source, (self._find_apple_music, self._find_tidal, self._find_vivimusic)
        )

    def _read_cached_result(self, cache_key: str) -> tuple[bool, CanvasArtwork | None]:
        with self._lock:
            cached = self._result_cache.get(cache_key)
            if cached is None:
                return False, None
            expires_at, artwork = cached
            if self._now() >= expires_at:
                del self._result_cache[cache_key]
                return False, None
            self._result_cache.move_to_end(cache_key)
            return True, artwork

    def _cache_result(self, cache_key: str, artwork: CanvasArtwork | None) -> None:
        with self._lock:
            self._result_cache[cache_key] = (self._now() + RESULT_CACHE_TTL, artwork)
            self._result_cache.move_to_end(cache_key)
            while len(self._result_cache) > MAX_RESULT_CACHE_ENTRIES:
                self._result_cache.popitem(last=False)

    def _find_vivimusic(self, query: CanvasQuery) -> CanvasArtwork | None:
        manifest = self._get_vivi_manifest()
        if not manifest or not query.album:
            return None
        candidates = [
            entry
            for entry in manifest
            if _normalize(_as_text(entry.get("album"))) == _normalize(query.album)
        ]
        best = _best_candidate(
            candidates,
            query,
            title=lambda entry: _as_text(entry.get("song")),
            artist=lambda entry: _as_text(entry.get("artist")),
        )
        url = _as_text(best.get("url")) if best else ""
        return CanvasArtwork("vivimusic", url) if _is_http_url(url) else None

    def _get_vivi_manifest(self) -> list[dict[str, object]]:
        with self._lock:
            if self._manifest is not None and self._now() < self._manifest_expires:
                return self._manifest
        try:
            response = self._get(VIVI_MANIFEST_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            entries = payload.get("items") if isinstance(payload, dict) else payload
            manifest: list[dict[str, object]] = (
                [entry for entry in entries if isinstance(entry, dict)]
                if isinstance(entries, list)
                else []
            )
        except (requests.RequestException, ValueError, AttributeError):
            manifest = []
        with self._lock:
            self._manifest = manifest
            self._manifest_expires = self._now() + MANIFEST_CACHE_TTL
        return manifest

    def _find_tidal(self, query: CanvasQuery) -> CanvasArtwork | None:
        try:
            response = self._get(
                TIDAL_API_URL,
                params={
                    "query": f"{query.title} {query.artist}".strip(),
                    "limit": 10,
                    "types": "TRACKS,ALBUMS",
                    "countryCode": _country_code(),
                },
                headers={"X-Tidal-Token": TIDAL_TOKEN},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, AttributeError):
            return None
        if not isinstance(payload, dict):
            return None

        candidates = [*self._tidal_items(payload, "tracks"), *self._tidal_items(payload, "albums")]
        candidates = [candidate for candidate in candidates if _tidal_video_cover(candidate)]
        best = _best_candidate(
            candidates,
            query,
            title=lambda entry: _as_text(entry.get("title") or entry.get("name")),
            artist=_tidal_artist_name,
        )
        if not best:
            return None
        video_cover = _tidal_video_cover(best)
        url = _tidal_video_url(video_cover)
        return CanvasArtwork("tidal", url) if url else None

    @staticmethod
    def _tidal_items(payload: dict[str, object], key: str) -> list[dict[str, object]]:
        collection = payload.get(key)
        if isinstance(collection, dict):
            collection = collection.get("items")
        return (
            [item for item in collection if isinstance(item, dict)]
            if isinstance(collection, list)
            else []
        )

    def _find_apple_music(self, query: CanvasQuery) -> CanvasArtwork | None:
        token = self._get_apple_token()
        if not token:
            return None
        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": APPLE_ORIGIN,
            "Referer": f"{APPLE_ORIGIN}/",
            "User-Agent": CHROME_USER_AGENT,
        }
        try:
            response = self._get(
                f"{APPLE_API_ROOT}/{_country_code().lower()}/search",
                params={
                    "term": f"{query.title} {query.artist}".strip(),
                    "types": "albums,songs",
                    "limit": 10,
                    "extend": "editorialVideo",
                    "include": "albums",
                },
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, AttributeError):
            return None
        if not isinstance(payload, dict):
            return None

        candidates = list(_apple_results(payload))
        best = _best_candidate(
            candidates,
            query,
            title=lambda entry: (
                _as_text((entry.get("attributes") or {}).get("name"))
                if isinstance(entry.get("attributes"), dict)
                else ""
            ),
            artist=lambda entry: (
                _as_text((entry.get("attributes") or {}).get("artistName"))
                if isinstance(entry.get("attributes"), dict)
                else ""
            ),
        )
        if not best:
            return None
        video_url = _apple_video_url(best)
        if video_url:
            return CanvasArtwork("apple_music", video_url)
        album_id = _apple_album_id(best)
        if not album_id:
            return None
        try:
            response = self._get(
                f"{APPLE_API_ROOT}/{_country_code().lower()}/albums/{album_id}",
                params={"extend": "editorialVideo", "include": "tracks"},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            album_payload = response.json()
        except (requests.RequestException, ValueError, AttributeError):
            return None
        if not isinstance(album_payload, dict):
            return None
        return next(
            (
                CanvasArtwork("apple_music", video_url)
                for entry in _apple_results(album_payload)
                if (video_url := _apple_video_url(entry))
            ),
            None,
        )

    def _get_apple_token(self) -> str | None:
        with self._lock:
            if self._apple_token and self._now() < self._apple_token_expires:
                return self._apple_token
        try:
            response = self._get(
                APPLE_BROWSE_URL,
                headers={"User-Agent": CHROME_USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            bundle_paths = BUNDLE_PATTERN.findall(response.text)
        except (requests.RequestException, AttributeError):
            return None
        for bundle_path in bundle_paths[:16]:
            try:
                response = self._get(
                    urljoin(APPLE_ORIGIN, bundle_path),
                    headers={"User-Agent": CHROME_USER_AGENT},
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
            except (requests.RequestException, AttributeError):
                continue
            for candidate in TOKEN_PATTERN.findall(response.text):
                expires_at = _apple_token_expiry(candidate)
                if expires_at <= self._now() + 60:
                    continue
                with self._lock:
                    self._apple_token = candidate
                    self._apple_token_expires = expires_at - 60
                return candidate
        return None


def query_from_payload(payload: object) -> CanvasQuery | None:
    """Validate the small public API contract accepted by the canvas route."""
    if not isinstance(payload, dict):
        return None
    title = _bounded_text(payload.get("title"), 300)
    artist = _bounded_text(payload.get("artist"), 300)
    album = _bounded_text(payload.get("album"), 300)
    duration = payload.get("durationSeconds")
    duration_seconds = (
        int(duration) if isinstance(duration, int | float) and 0 < duration <= 86_400 else None
    )
    source = _as_text(payload.get("source"))
    source = source if source in {"auto", "apple_music", "tidal", "vivimusic"} else "auto"
    return CanvasQuery(title, artist, album, duration_seconds, source) if title and artist else None


def _bounded_text(value: object, maximum: int) -> str:
    return value.strip()[:maximum] if isinstance(value, str) else ""


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_diacritics = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", without_diacritics.casefold()).split())


def _country_code() -> str:
    locale_name = locale.getlocale()[0] or ""
    match = re.search(r"[_-]([a-zA-Z]{2})$", locale_name)
    return match.group(1).upper() if match else "US"


def _as_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _best_candidate(
    candidates: Iterable[dict[str, object]],
    query: CanvasQuery,
    title: Callable[[dict[str, object]], str],
    artist: Callable[[dict[str, object]], str],
) -> dict[str, object] | None:
    best: dict[str, object] | None = None
    best_score = 0.0
    for candidate in candidates:
        title_score = _similarity(query.title, title(candidate))
        artist_score = _similarity(query.artist, artist(candidate))
        score = title_score * 0.7 + artist_score * 0.3
        if score >= 0.72 and score > best_score:
            best = candidate
            best_score = score
    return best


def _similarity(left: str, right: str) -> float:
    normalized_left = _normalize(left)
    normalized_right = _normalize(right)
    if (
        normalized_left
        and normalized_right
        and (normalized_left in normalized_right or normalized_right in normalized_left)
    ):
        return 0.9
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def _tidal_video_url(video_cover: str) -> str | None:
    parts = video_cover.split("-")
    if len(parts) != 5 or not all(parts):
        return None
    return f"https://resources.tidal.com/videos/{'/'.join(parts)}/1280x1280.mp4"


def _tidal_video_cover(entry: dict[str, object]) -> str:
    album = entry.get("album") if isinstance(entry.get("album"), dict) else entry
    return _as_text(album.get("videoCover")) if isinstance(album, dict) else ""


def _tidal_artist_name(entry: dict[str, object]) -> str:
    artist = entry.get("artist")
    if isinstance(artist, dict):
        return _as_text(artist.get("name"))
    artists = entry.get("artists")
    if isinstance(artists, list):
        return ", ".join(_as_text(item.get("name")) for item in artists if isinstance(item, dict))
    return _as_text(entry.get("artistName"))


def _apple_token_expiry(token: str) -> float:
    try:
        payload = token.split(".")[1]
        padding = "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload + padding))
        expiry = decoded.get("exp") if isinstance(decoded, dict) else None
        issuer = decoded.get("iss") if isinstance(decoded, dict) else None
        return float(expiry) if issuer == "AMPWebPlay" and isinstance(expiry, int | float) else 0.0
    except (ValueError, IndexError, UnicodeDecodeError, json.JSONDecodeError):
        return 0.0


def _apple_results(payload: dict[str, object]) -> Iterable[dict[str, object]]:
    results = payload.get("results")
    if not isinstance(results, dict):
        results = {"data": payload.get("data")}
    for group in results.values():
        entries = group.get("data") if isinstance(group, dict) else group
        if isinstance(entries, list):
            yield from (entry for entry in entries if isinstance(entry, dict))


def _apple_album_id(entry: dict[str, object]) -> str:
    if entry.get("type") == "albums":
        return _as_text(entry.get("id"))
    relationships = entry.get("relationships")
    albums = relationships.get("albums") if isinstance(relationships, dict) else None
    data = albums.get("data") if isinstance(albums, dict) else None
    return (
        _as_text(data[0].get("id"))
        if isinstance(data, list) and data and isinstance(data[0], dict)
        else ""
    )


def _apple_video_url(entry: dict[str, object]) -> str | None:
    attributes = entry.get("attributes")
    editorial_video = attributes.get("editorialVideo") if isinstance(attributes, dict) else None
    return _find_url(editorial_video)


def _find_url(value: object) -> str | None:
    if isinstance(value, str):
        return value if _is_http_url(value) else None
    if isinstance(value, dict):
        for key in ("video", "videoUrl", "hlsUrl", "url"):
            found = _find_url(value.get(key))
            if found:
                return found
        for nested in value.values():
            found = _find_url(nested)
            if found:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_url(nested)
            if found:
                return found
    return None


def _is_http_url(value: str) -> bool:
    return value.startswith("https://") or value.startswith("http://")
