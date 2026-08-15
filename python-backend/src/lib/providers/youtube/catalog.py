"""Read-only YouTube Music catalog adapter."""

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, cast

import requests

from src.lib.music.audio_versions import prefer_audio_versions
from src.lib.music.video_variants import is_video_variant
from src.lib.music.youtube_data import YoutubeResponseMapper
from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.runtime.metadata_cache import MetadataCache

from ..errors import (
    ProviderAuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from ..models import (
    CatalogAlbum,
    CatalogAlbumSummary,
    CatalogArtist,
    CatalogArtistReference,
    CatalogPlaylist,
    CatalogSearchFilter,
    CatalogSearchQuery,
    CatalogSearchResult,
    CatalogSong,
    CatalogTrack,
)

type YoutubeSearchFilter = Literal[
    "albums",
    "artists",
    "community_playlists",
    "episodes",
    "featured_playlists",
    "playlists",
    "podcasts",
    "profiles",
    "songs",
    "videos",
]


class YoutubeCatalogClient(Protocol):
    """The untyped ytmusicapi operations used by this capability."""

    def search(
        self,
        query: str,
        filter: YoutubeSearchFilter | None = "songs",
        limit: int = 20,
    ) -> object: ...

    def get_album(self, browse_id: str) -> object: ...


class YoutubeMusicCatalogProvider:
    """Normalize ytmusicapi catalog payloads behind a narrow typed boundary."""

    def __init__(
        self,
        session: YoutubeMusicSession,
        metadata_cache: MetadataCache | None = None,
    ) -> None:
        self._session = session
        self._metadata_cache = metadata_cache

    def search(self, query: CatalogSearchQuery) -> list[CatalogSearchResult]:
        client = self._active_client()
        provider_filter = self._provider_filter(query.filter)
        try:
            raw_results = client.search(
                query.text,
                filter=provider_filter,
                limit=query.limit,
            )
        except requests.RequestException:
            raise ProviderUnavailableError() from None
        except Exception:
            raise ProviderResponseError() from None

        if not isinstance(raw_results, list):
            raise ProviderResponseError()
        return [
            normalized
            for entry in raw_results
            if isinstance(entry, Mapping)
            and (normalized := self._search_result(entry, query.filter)) is not None
        ]

    def suggestions(self, query: str, limit: int) -> list[str]:
        client = self._active_client()
        try:
            raw_results = client.search(query, filter=None, limit=limit)
        except requests.RequestException:
            raise ProviderUnavailableError() from None
        except Exception:
            raise ProviderResponseError() from None

        if not isinstance(raw_results, list):
            raise ProviderResponseError()
        return [
            title
            for entry in raw_results
            if isinstance(entry, Mapping) and (title := self._text(entry.get("title")))
        ]

    def album(self, browse_id: str) -> CatalogAlbum:
        client = self._active_client()
        try:
            raw_album = client.get_album(browse_id)
        except requests.RequestException:
            raise ProviderUnavailableError() from None
        except Exception:
            raise ProviderResponseError() from None

        if not isinstance(raw_album, Mapping):
            raise ProviderResponseError()

        title = self._text(raw_album.get("title"))
        artists = self._artists(raw_album.get("artists"))
        thumbnail = YoutubeResponseMapper.select_thumbnail(raw_album.get("thumbnails"))
        raw_tracks = self._mapping_items(raw_album.get("tracks"))
        playable_tracks = [track for track in raw_tracks if self._text(track.get("videoId"))]
        resolved_tracks = self._resolve_album_tracks(playable_tracks)
        tracks = tuple(
            track
            for raw_track in resolved_tracks
            if (track := self._album_track(raw_track, artists)) is not None
        )
        return CatalogAlbum(
            browse_id=browse_id,
            title=title,
            artists=artists,
            year=self._text(raw_album.get("year")),
            thumbnail=thumbnail,
            tracks=tracks,
        )

    def _resolve_album_tracks(self, tracks: list[Mapping[str, object]]) -> list[dict[str, object]]:
        if not any(is_video_variant(track) for track in tracks):
            return [dict(track) for track in tracks]
        try:
            return prefer_audio_versions(
                self._session.get_system_client(),
                None,
                tracks,
                self._metadata_cache,
            )
        except requests.RequestException:
            raise ProviderUnavailableError() from None
        except Exception:
            raise ProviderResponseError() from None

    def _active_client(self) -> YoutubeCatalogClient:
        try:
            return cast("YoutubeCatalogClient", self._session.get_active_client())
        except Exception:
            raise ProviderAuthenticationError() from None

    @staticmethod
    def _provider_filter(search_filter: CatalogSearchFilter) -> YoutubeSearchFilter | None:
        if search_filter is CatalogSearchFilter.ALL:
            return None
        return cast("YoutubeSearchFilter", search_filter.value)

    def _search_result(
        self,
        raw: Mapping[str, object],
        search_filter: CatalogSearchFilter,
    ) -> CatalogSearchResult | None:
        result_type = self._text(raw.get("resultType")) or self._fallback_result_type(search_filter)
        if result_type == "song":
            return self._song(raw)
        if result_type == "artist":
            return self._artist(raw)
        if result_type == "album":
            return self._album_summary(raw)
        if result_type == "playlist":
            return self._playlist(raw)
        return None

    def _song(self, raw: Mapping[str, object]) -> CatalogSong | None:
        video_id = self._text(raw.get("videoId"))
        title = self._text(raw.get("title"))
        if not video_id or not title:
            return None
        album = raw.get("album")
        album_mapping = album if isinstance(album, Mapping) else {}
        return CatalogSong(
            video_id=video_id,
            title=title,
            artists=self._artists(raw.get("artists"), drop_type_label=True),
            album=self._text(album_mapping.get("name")),
            album_browse_id=self._text(album_mapping.get("id")),
            duration=self._text(raw.get("duration")),
            thumbnail=YoutubeResponseMapper.select_thumbnail(raw.get("thumbnails")),
            is_explicit=raw.get("isExplicit") is True,
        )

    def _artist(self, raw: Mapping[str, object]) -> CatalogArtist | None:
        top_artists = self._artists(raw.get("artists"))
        top_artist = top_artists[0] if top_artists else CatalogArtistReference("")
        browse_id = (
            self._text(raw.get("browseId"))
            or self._text(raw.get("channelId"))
            or top_artist.browse_id
        )
        title = self._text(raw.get("title")) or self._text(raw.get("artist")) or top_artist.name
        if not browse_id or not title:
            return None
        return CatalogArtist(
            browse_id=browse_id,
            title=title,
            subscribers=self._text(raw.get("subscribers")),
            thumbnail=YoutubeResponseMapper.select_thumbnail(raw.get("thumbnails")),
        )

    def _album_summary(self, raw: Mapping[str, object]) -> CatalogAlbumSummary | None:
        browse_id = self._text(raw.get("browseId"))
        title = self._text(raw.get("title"))
        if not browse_id or not title:
            return None
        artists = self._artists(raw.get("artists"))
        fallback_artist = self._text(raw.get("artist"))
        if not artists and fallback_artist:
            artists = (CatalogArtistReference(fallback_artist),)
        return CatalogAlbumSummary(
            browse_id=browse_id,
            title=title,
            artists=artists,
            year=self._text(raw.get("year")),
            thumbnail=YoutubeResponseMapper.select_thumbnail(raw.get("thumbnails")),
        )

    def _playlist(self, raw: Mapping[str, object]) -> CatalogPlaylist | None:
        browse_id = self._text(raw.get("browseId"))
        playlist_id = self._text(raw.get("playlistId")) or browse_id.removeprefix("VL")
        title = self._text(raw.get("title"))
        if not playlist_id or not title:
            return None
        return CatalogPlaylist(
            playlist_id=playlist_id.removeprefix("VL"),
            browse_id=browse_id,
            title=title,
            author=self._text(raw.get("author")),
            thumbnail=YoutubeResponseMapper.select_thumbnail(raw.get("thumbnails")),
        )

    def _album_track(
        self,
        raw: Mapping[str, object],
        album_artists: tuple[CatalogArtistReference, ...],
    ) -> CatalogTrack | None:
        video_id = self._text(raw.get("videoId"))
        title = self._text(raw.get("title"))
        if not video_id or not title:
            return None
        artists = self._artists(raw.get("artists")) or album_artists
        return CatalogTrack(
            video_id=video_id,
            title=title,
            artists=artists,
            duration=self._text(raw.get("duration")),
            is_explicit=raw.get("isExplicit") is True,
        )

    @staticmethod
    def _fallback_result_type(search_filter: CatalogSearchFilter) -> str:
        return {
            CatalogSearchFilter.ALBUMS: "album",
            CatalogSearchFilter.ARTISTS: "artist",
            CatalogSearchFilter.COMMUNITY_PLAYLISTS: "playlist",
            CatalogSearchFilter.FEATURED_PLAYLISTS: "playlist",
            CatalogSearchFilter.PLAYLISTS: "playlist",
            CatalogSearchFilter.SONGS: "song",
        }.get(search_filter, "")

    @staticmethod
    def _text(value: object) -> str:
        return value if isinstance(value, str) else ""

    @staticmethod
    def _mapping_items(value: object) -> list[Mapping[str, object]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return []
        return [item for item in value if isinstance(item, Mapping)]

    def _artists(
        self,
        value: object,
        *,
        drop_type_label: bool = False,
    ) -> tuple[CatalogArtistReference, ...]:
        raw_artists = (
            YoutubeResponseMapper.drop_type_label_artist(value)
            if drop_type_label
            else self._mapping_items(value)
        )
        return tuple(
            CatalogArtistReference(
                name=name,
                browse_id=self._text(artist.get("id")) or self._text(artist.get("browseId")),
            )
            for artist in raw_artists
            if (name := self._text(artist.get("name")))
        )
