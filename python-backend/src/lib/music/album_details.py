"""Cached album-detail orchestration and response formatting."""

from typing import Protocol

from src.lib.providers.contracts import MusicCatalogProvider
from src.lib.providers.models import CatalogAlbum, CatalogArtistReference


class AlbumResponseCache(Protocol):
    """Persist the existing album response representation by browse id."""

    def load_album_disk(self, browse_id: str) -> dict[str, object] | None: ...

    def save_album_disk(self, browse_id: str, data: dict[str, object]) -> None: ...


class AlbumCacheSettings(Protocol):
    """Expose runtime cache-category enablement."""

    enabled: dict[str, bool]


class AlbumDetailsService:
    """Load normalized albums and own all album response caching decisions."""

    def __init__(
        self,
        catalog: MusicCatalogProvider,
        album_cache: AlbumResponseCache,
        cache_settings: AlbumCacheSettings,
    ) -> None:
        self._catalog = catalog
        self._album_cache = album_cache
        self._cache_settings = cache_settings

    def get(self, browse_id: str, *, force_refresh: bool = False) -> dict[str, object]:
        cache_enabled = self._cache_settings.enabled.get("albums", False)
        if cache_enabled and not force_refresh:
            cached = self._album_cache.load_album_disk(browse_id)
            if cached is not None:
                return cached

        result = self._response(self._catalog.album(browse_id))
        if cache_enabled:
            self._album_cache.save_album_disk(browse_id, result)
        return result

    @classmethod
    def _response(cls, album: CatalogAlbum) -> dict[str, object]:
        artist_name = cls._artist_names(album.artists)
        artist_browse_id = cls._first_artist_id(album.artists)
        return {
            "title": album.title,
            "artists": artist_name,
            "artistBrowseId": artist_browse_id,
            "year": album.year,
            "thumbnail": album.thumbnail,
            "tracks": [
                {
                    "videoId": track.video_id,
                    "title": track.title,
                    "artists": cls._artist_names(track.artists),
                    "artistBrowseId": cls._first_artist_id(track.artists),
                    "artistLinks": [
                        {"name": artist.name, "browseId": artist.browse_id}
                        for artist in track.artists
                    ],
                    "album": album.title,
                    "duration": track.duration,
                    "thumbnail": album.thumbnail,
                    "isExplicit": track.is_explicit,
                }
                for track in album.tracks
            ],
        }

    @staticmethod
    def _artist_names(artists: tuple[CatalogArtistReference, ...]) -> str:
        return ", ".join(artist.name for artist in artists)

    @staticmethod
    def _first_artist_id(artists: tuple[CatalogArtistReference, ...]) -> str:
        return artists[0].browse_id if artists else ""
