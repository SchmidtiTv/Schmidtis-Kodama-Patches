"""YouTube Music playlist capability and account-track enrichment adapter."""

from collections.abc import Iterator, Mapping
from typing import Protocol, cast

from src.lib.music.audio_versions import iter_preferred_audio_versions, prefer_audio_versions
from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.providers.errors import ProviderAuthenticationError, ProviderResponseError
from src.lib.providers.models import (
    AddPlaylistItems,
    CreatedPlaylist,
    CreatePlaylist,
    EditPlaylist,
    LikedSong,
    PlaylistDetails,
    PlaylistRadio,
    PlaylistTrack,
    RemovePlaylistItems,
)
from src.lib.runtime.metadata_cache import MetadataCache

from ._account_errors import call_youtube
from ._account_mapping import mapping_items, playlist_track, text, track_payload


class YoutubePlaylistClient(Protocol):
    def get_playlist(self, playlist_id: str, limit: int | None = None) -> object: ...

    def get_liked_songs(self, limit: int | None = None) -> object: ...

    def create_playlist(
        self,
        title: str,
        description: str,
        privacy_status: str,
        video_ids: list[str],
    ) -> object: ...

    def edit_playlist(self, playlist_id: str, **values: object) -> object: ...

    def delete_playlist(self, playlist_id: str) -> object: ...

    def add_playlist_items(self, playlist_id: str, video_ids: list[str]) -> object: ...

    def remove_playlist_items(self, playlist_id: str, videos: list[dict[str, str]]) -> object: ...

    def get_watch_playlist(self, **values: object) -> object: ...


class YoutubeMusicPlaylistProvider:
    """Normalize account playlist operations behind typed commands."""

    def __init__(self, session: YoutubeMusicSession) -> None:
        self._session = session

    def get(self, playlist_id: str) -> PlaylistDetails:
        if playlist_id == "LM":
            raw = call_youtube(lambda: self._client().get_liked_songs())
            title = "Liked Songs"
            thumbnail = ""
        else:
            raw = call_youtube(lambda: self._client().get_playlist(playlist_id, limit=None))
            title = text(raw.get("title")) if isinstance(raw, Mapping) else ""
            raw_thumbnails = (
                mapping_items(raw.get("thumbnails")) if isinstance(raw, Mapping) else []
            )
            thumbnail = text(raw_thumbnails[-1].get("url")) if raw_thumbnails else ""
        if not isinstance(raw, Mapping):
            raise ProviderResponseError()
        tracks = tuple(
            track
            for item in mapping_items(raw.get("tracks"))
            if (track := playlist_track(item)) is not None
        )
        return PlaylistDetails(title, thumbnail, tracks)

    def create(self, command: CreatePlaylist) -> CreatedPlaylist:
        result = call_youtube(
            lambda: self._client().create_playlist(
                command.title,
                command.description,
                privacy_status=command.privacy.value,
                video_ids=list(command.video_ids),
            )
        )
        playlist_id = text(result)
        if not playlist_id:
            raise ProviderResponseError()
        return CreatedPlaylist(playlist_id)

    def edit(self, command: EditPlaylist) -> None:
        call_youtube(
            lambda: self._client().edit_playlist(
                command.playlist_id,
                title=command.title,
                description=command.description,
                privacyStatus=command.privacy.value if command.privacy else None,
            )
        )

    def delete(self, playlist_id: str) -> None:
        call_youtube(lambda: self._client().delete_playlist(playlist_id))

    def add_items(self, command: AddPlaylistItems) -> None:
        call_youtube(
            lambda: self._client().add_playlist_items(command.playlist_id, list(command.video_ids))
        )

    def remove_items(self, command: RemovePlaylistItems) -> None:
        items = [
            {"videoId": item.video_id, "setVideoId": item.set_video_id} for item in command.items
        ]
        call_youtube(lambda: self._client().remove_playlist_items(command.playlist_id, items))

    def radio(self, playlist_id: str) -> PlaylistRadio:
        raw = call_youtube(
            lambda: self._client().get_watch_playlist(playlistId=playlist_id, limit=50)
        )
        return self._radio_result(raw)

    def song_radio(self, video_id: str) -> PlaylistRadio:
        raw = call_youtube(
            lambda: self._client().get_watch_playlist(
                videoId=video_id,
                limit=50,
                radio=True,
            )
        )
        return self._radio_result(raw)

    @staticmethod
    def _radio_result(raw: object) -> PlaylistRadio:
        if not isinstance(raw, Mapping):
            raise ProviderResponseError()
        return PlaylistRadio(
            tuple(
                track
                for item in mapping_items(raw.get("tracks"))
                if (track := playlist_track(item)) is not None
            )
        )

    def _client(self) -> YoutubePlaylistClient:
        try:
            return cast("YoutubePlaylistClient", self._session.get_active_client())
        except Exception:
            raise ProviderAuthenticationError() from None


class YoutubePlaylistAudioEnricher:
    """Adapt the anonymous resolver client without exposing it to services."""

    def __init__(self, session: YoutubeMusicSession, cache: MetadataCache) -> None:
        self._session = session
        self._cache = cache

    def enrich(
        self, playlist_id: str | None, tracks: tuple[PlaylistTrack, ...]
    ) -> tuple[PlaylistTrack, ...]:
        raw = [track_payload(track) for track in tracks]
        resolved = call_youtube(
            lambda: prefer_audio_versions(
                self._session.get_system_client(), playlist_id, raw, self._cache
            )
        )
        return tuple(track for item in resolved if (track := playlist_track(item)) is not None)

    def iter_enriched(
        self,
        playlist_id: str | None,
        tracks: tuple[PlaylistTrack, ...],
        batch_size: int,
    ) -> Iterator[tuple[PlaylistTrack, ...]]:
        raw = [track_payload(track) for track in tracks]
        iterator = call_youtube(
            lambda: iter_preferred_audio_versions(
                self._session.get_system_client(),
                playlist_id,
                raw,
                batch_size,
                self._cache,
            )
        )
        while True:
            try:
                batch = call_youtube(lambda: next(iterator))
            except StopIteration:
                return
            yield tuple(track for item in batch if (track := playlist_track(item)) is not None)

    def enrich_liked(self, tracks: tuple[LikedSong, ...]) -> tuple[LikedSong, ...]:
        playlist_tracks = tuple(
            PlaylistTrack(
                video_id=track.video_id,
                set_video_id="",
                title=track.title,
                artists=track.artist_links,
                album=track.album,
                album_browse_id=track.album_browse_id,
                duration=track.duration,
                thumbnails=(track.thumbnail,) if track.thumbnail else (),
                is_explicit=track.is_explicit,
                video_type=track.video_type,
                is_detected_video=track.is_detected_video,
            )
            for track in tracks
        )
        enriched = self.enrich(None, playlist_tracks)
        return tuple(
            LikedSong(
                video_id=track.video_id,
                title=track.title,
                artists=", ".join(artist.name for artist in track.artists),
                artist_browse_id=track.artists[0].browse_id if track.artists else "",
                artist_links=track.artists,
                album=track.album,
                album_browse_id=track.album_browse_id,
                duration=track.duration,
                thumbnail=track.thumbnails[0] if track.thumbnails else "",
                is_explicit=track.is_explicit,
                video_type=track.video_type,
                is_detected_video=track.is_detected_video,
            )
            for track in enriched
        )
