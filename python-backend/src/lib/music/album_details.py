"""Resolves an artist/album pair to canonical release details via MusicBrainz."""

from __future__ import annotations

from typing import Any

from src.config import Config
from src.lib.integrations.musicbrainz import MusicBrainz, MusicBrainzError
from src.lib.runtime.metadata_cache import MetadataCache

COVER_ART_URL = "https://coverartarchive.org/release"


class AlbumDetailsError(Exception):
    """Raised when album details cannot be resolved from MusicBrainz."""


class AlbumDetailsFinder:
    """Finds the best-matching MusicBrainz release for an artist/album pair.

    MusicBrainz's release search scores each candidate 0-100; the top-scoring
    result is treated as the match and expanded into its full tracklist,
    label info, and artist credit.
    """

    _CACHE_CATEGORY = "musicbrainz_album_details"
    # Marks a cached "no matching release" outcome so a known-missing album doesn't keep paying
    # the MusicBrainz round trip on every panel open either.
    _NOT_FOUND_MARKER = "_not_found"

    def __init__(
        self,
        musicbrainz: MusicBrainz | None = None,
        metadata_cache: MetadataCache | None = None,
    ) -> None:
        self._musicbrainz = musicbrainz or MusicBrainz()
        self._metadata_cache = metadata_cache

    def find(self, artist: str, album: str) -> dict[str, Any] | None:
        cache_key = self._cache_key(artist, album)
        if self._metadata_cache is not None:
            cached = self._metadata_cache.get(
                self._CACHE_CATEGORY, cache_key, Config.MUSICBRAINZ_ALBUM_CACHE_TTL
            )
            if cached is not None:
                return None if cached.get(self._NOT_FOUND_MARKER) else cached

        try:
            release_id = self._best_match_id(artist, album)
            if release_id is None:
                self._store(cache_key, {self._NOT_FOUND_MARKER: True})
                return None
            release = self._musicbrainz.get_release(release_id)
        except MusicBrainzError as error:
            raise AlbumDetailsError from error
        shaped = self._shape(release)
        self._store(cache_key, shaped)
        return shaped

    @staticmethod
    def _cache_key(artist: str, album: str) -> str:
        return f"{artist.strip().casefold()}|{album.strip().casefold()}"

    def _store(self, cache_key: str, value: dict[str, Any]) -> None:
        if self._metadata_cache is not None:
            self._metadata_cache.put(self._CACHE_CATEGORY, cache_key, value)

    def _best_match_id(self, artist: str, album: str) -> str | None:
        query = f'release:"{album}" AND artist:"{artist}"'
        candidates = [
            release
            for release in self._musicbrainz.search_releases(query, limit=5)
            if isinstance(release, dict)
        ]
        if not candidates:
            return None
        best = max(candidates, key=self._score)
        release_id = best.get("id")
        return release_id if isinstance(release_id, str) else None

    @staticmethod
    def _score(release: dict[str, Any]) -> float:
        score = release.get("score")
        return score if isinstance(score, (int, float)) else 0

    @staticmethod
    def _shape(release: dict[str, Any]) -> dict[str, Any]:
        tracks: list[dict[str, Any]] = []
        media = release.get("media", [])
        for medium in media if isinstance(media, list) else []:
            medium_tracks = medium.get("tracks", []) if isinstance(medium, dict) else []
            for track in medium_tracks if isinstance(medium_tracks, list) else []:
                if not isinstance(track, dict):
                    continue
                tracks.append(
                    {
                        "title": track.get("title", ""),
                        "position": track.get("position"),
                        "durationMs": track.get("length"),
                    }
                )

        labels: list[str] = []
        catalog_numbers: list[str] = []
        label_info = release.get("label-info", [])
        for entry in label_info if isinstance(label_info, list) else []:
            if not isinstance(entry, dict):
                continue
            label = entry.get("label")
            name = label.get("name") if isinstance(label, dict) else None
            if isinstance(name, str) and name:
                labels.append(name)
            catalog_number = entry.get("catalog-number")
            if isinstance(catalog_number, str) and catalog_number:
                catalog_numbers.append(catalog_number)

        artist_credit = release.get("artist-credit", [])
        artists = ", ".join(
            credit.get("name", "")
            for credit in (artist_credit if isinstance(artist_credit, list) else [])
            if isinstance(credit, dict) and credit.get("name")
        )

        release_id = release.get("id", "")
        return {
            "id": release_id,
            "title": release.get("title", ""),
            "date": release.get("date", ""),
            "artists": artists,
            "labels": labels,
            "catalogNumbers": catalog_numbers,
            "tracks": tracks,
            "coverArtUrl": f"{COVER_ART_URL}/{release_id}/front-500" if release_id else "",
        }
