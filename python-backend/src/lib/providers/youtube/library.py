"""Authenticated YouTube Music library capability."""

from collections.abc import Mapping
from typing import Protocol, cast

from src.lib.music.youtube_data import YoutubeResponseMapper
from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.providers.errors import ProviderAuthenticationError, ProviderResponseError
from src.lib.providers.models import (
    LibraryAlbum,
    LibraryArtist,
    LibraryPlaylist,
    LikedSongsPage,
    LikedSongsQuery,
    SongRating,
)

from ._account_errors import call_youtube
from ._account_mapping import liked_song, mapping_items, text


class YoutubeLibraryClient(Protocol):
    def get_library_albums(self, limit: int | None = None) -> object: ...

    def get_library_artists(self, limit: int | None = None) -> object: ...

    def get_library_playlists(self, limit: int | None = None) -> object: ...

    def get_liked_songs(self, limit: int | None = None) -> object: ...

    def rate_song(self, video_id: str, rating: str) -> object: ...

    def subscribe_artists(self, channel_ids: list[str]) -> object: ...

    def unsubscribe_artists(self, channel_ids: list[str]) -> object: ...

    def get_song(self, video_id: str) -> object: ...

    def add_history_item(self, song: object) -> object: ...


class YoutubeMusicLibraryProvider:
    """Keep raw library dictionaries within a concrete YouTube adapter."""

    def __init__(self, session: YoutubeMusicSession) -> None:
        self._session = session

    def albums(self) -> tuple[LibraryAlbum, ...]:
        raw = call_youtube(lambda: self._client().get_library_albums(limit=None))
        return tuple(
            LibraryAlbum(
                browse_id=text(album.get("browseId")),
                title=text(album.get("title")),
                artists=", ".join(
                    text(artist.get("name")) for artist in mapping_items(album.get("artists"))
                ),
                year=text(album.get("year")),
                thumbnail=YoutubeResponseMapper.select_thumbnail(album.get("thumbnails")),
            )
            for album in mapping_items(raw)
        )

    def artists(self) -> tuple[LibraryArtist, ...]:
        raw = call_youtube(lambda: self._client().get_library_artists(limit=None))
        return tuple(
            LibraryArtist(
                browse_id=text(artist.get("browseId")),
                artist=text(artist.get("artist")),
                songs=text(artist.get("songs")),
                thumbnail=YoutubeResponseMapper.select_thumbnail(artist.get("thumbnails")),
            )
            for artist in mapping_items(raw)
        )

    def playlists(self) -> tuple[LibraryPlaylist, ...]:
        raw = call_youtube(lambda: self._client().get_library_playlists(limit=None))
        return tuple(
            LibraryPlaylist(
                playlist_id=text(playlist.get("playlistId")),
                title=text(playlist.get("title")),
                count=text(playlist.get("count")),
                thumbnail=YoutubeResponseMapper.select_thumbnail(playlist.get("thumbnails")),
            )
            for playlist in mapping_items(raw)
            if text(playlist.get("playlistId")) != "LM"
        )

    def liked_songs(self, query: LikedSongsQuery) -> LikedSongsPage:
        raw = call_youtube(lambda: self._client().get_liked_songs(limit=query.offset + query.limit))
        if not isinstance(raw, Mapping):
            raise ProviderResponseError()
        raw_tracks = mapping_items(raw.get("tracks"))
        page = raw_tracks[query.offset : query.offset + query.limit]
        tracks = tuple(track for item in page if (track := liked_song(item)) is not None)
        raw_total = raw.get("trackCount", len(raw_tracks))
        try:
            total = int(raw_total)
        except (TypeError, ValueError):
            total = len(raw_tracks)
        return LikedSongsPage(
            tracks=tracks,
            total=total,
            offset=query.offset,
            has_more=query.offset + len(tracks) < total,
        )

    def liked_song_ids(self) -> frozenset[str]:
        raw = call_youtube(lambda: self._client().get_liked_songs())
        if not isinstance(raw, Mapping):
            raise ProviderResponseError()
        return frozenset(
            video_id
            for track in mapping_items(raw.get("tracks"))
            if (video_id := text(track.get("videoId")))
        )

    def rate_song(self, video_id: str, rating: SongRating) -> None:
        call_youtube(lambda: self._client().rate_song(video_id, rating.value))

    def subscribe_artist(self, browse_id: str) -> None:
        call_youtube(lambda: self._client().subscribe_artists([browse_id]))

    def unsubscribe_artist(self, browse_id: str) -> None:
        call_youtube(lambda: self._client().unsubscribe_artists([browse_id]))

    def add_history_item(self, video_id: str) -> None:
        song = call_youtube(lambda: self._client().get_song(video_id))
        if not isinstance(song, Mapping):
            raise ProviderResponseError()
        tracking = song.get("playbackTracking")
        if not isinstance(tracking, Mapping) or not tracking.get("videostatsPlaybackUrl"):
            raise ProviderResponseError()
        response = call_youtube(lambda: self._client().add_history_item(song))
        if getattr(response, "status_code", None) != 204:
            raise ProviderResponseError()

    def _client(self) -> YoutubeLibraryClient:
        try:
            return cast("YoutubeLibraryClient", self._session.get_active_client())
        except Exception:
            raise ProviderAuthenticationError() from None
