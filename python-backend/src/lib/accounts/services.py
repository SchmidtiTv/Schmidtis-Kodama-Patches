"""Use-case services for active-profile library and playlist behavior."""

from collections.abc import Callable, Iterator, Mapping
from typing import Protocol

from src.lib.music.playlist import Playlist
from src.lib.providers.contracts import MusicLibraryProvider, PlaylistProvider
from src.lib.providers.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderUnavailableError,
)
from src.lib.providers.models import (
    AddPlaylistItems,
    CatalogArtistReference,
    CreatedPlaylist,
    CreatePlaylist,
    EditPlaylist,
    LibraryAlbum,
    LibraryArtist,
    LibraryPlaylist,
    LikedSong,
    LikedSongsPage,
    LikedSongsQuery,
    PlaylistDetails,
    PlaylistRadio,
    PlaylistTrack,
    RemovePlaylistItems,
    SongRating,
)
from src.lib.runtime.cache import CacheSettings

from .context import ActiveMusicProfile
from .errors import (
    AccountConflictError,
    AccountProviderUnavailableError,
    AuthenticationRequiredError,
    LocalOperationNotSupportedError,
)
from .repositories import LocalMusicRepository

_TRANSFER_CHUNK_SIZE = 200
_RESOLUTION_BATCH_SIZE = 4


class PlaylistAudioEnricher(Protocol):
    def enrich(
        self, playlist_id: str | None, tracks: tuple[PlaylistTrack, ...]
    ) -> tuple[PlaylistTrack, ...]: ...

    def iter_enriched(
        self,
        playlist_id: str | None,
        tracks: tuple[PlaylistTrack, ...],
        batch_size: int,
    ) -> Iterator[tuple[PlaylistTrack, ...]]: ...

    def enrich_liked(self, tracks: tuple[LikedSong, ...]) -> tuple[LikedSong, ...]: ...


class SongRadioProvider(Protocol):
    def song_radio(self, video_id: str) -> PlaylistRadio: ...


class LibraryService:
    def __init__(
        self,
        profile_context: ActiveMusicProfile,
        remote_library: MusicLibraryProvider,
        local_library: LocalMusicRepository,
    ) -> None:
        self._profile = profile_context
        self._remote = remote_library
        self._local = local_library

    def albums(self) -> tuple[LibraryAlbum, ...]:
        if self._profile.is_local:
            return ()
        return _provider_call(self._remote.albums)

    def artists(self) -> tuple[LibraryArtist, ...]:
        if self._profile.is_local:
            return ()
        return _provider_call(self._remote.artists)

    def playlists(self) -> tuple[LibraryPlaylist, ...]:
        profile_name = self._profile.name
        if self._profile.is_local:
            return self._local.library_playlists(profile_name)
        return _provider_call(self._remote.playlists)


class LikedSongsService:
    def __init__(
        self,
        profile_context: ActiveMusicProfile,
        remote_library: MusicLibraryProvider,
        local_library: LocalMusicRepository,
        audio_enricher: PlaylistAudioEnricher,
    ) -> None:
        self._profile = profile_context
        self._remote = remote_library
        self._local = local_library
        self._audio = audio_enricher

    def songs(self, query: LikedSongsQuery) -> LikedSongsPage:
        profile_name = self._profile.name
        if self._profile.is_local:
            return LikedSongsPage(self._local.liked_songs(profile_name))
        page = _provider_call(lambda: self._remote.liked_songs(query))
        tracks = _provider_call(lambda: self._audio.enrich_liked(page.tracks))
        return LikedSongsPage(tracks, page.total, page.offset, page.has_more)

    def ids(self) -> frozenset[str]:
        profile_name = self._profile.name
        if self._profile.is_local:
            return self._local.liked_song_ids(profile_name)
        return _provider_call(self._remote.liked_song_ids)


class SongRatingService:
    def __init__(
        self,
        profile_context: ActiveMusicProfile,
        remote_library: MusicLibraryProvider,
        local_library: LocalMusicRepository,
    ) -> None:
        self._profile = profile_context
        self._remote = remote_library
        self._local = local_library

    def rate(
        self,
        video_id: str,
        rating: SongRating,
        metadata: dict[str, str],
    ) -> None:
        profile_name = self._profile.name
        if self._profile.is_local:
            self._local.rate_song(profile_name, video_id, rating, metadata)
            return
        _provider_call(lambda: self._remote.rate_song(video_id, rating))


class ArtistSubscriptionService:
    def __init__(
        self,
        profile_context: ActiveMusicProfile,
        remote_library: MusicLibraryProvider,
    ) -> None:
        self._profile = profile_context
        self._remote = remote_library

    def subscribe(self, browse_id: str) -> None:
        if self._profile.is_local:
            raise LocalOperationNotSupportedError()
        _provider_call(lambda: self._remote.subscribe_artist(browse_id))

    def unsubscribe(self, browse_id: str) -> None:
        if self._profile.is_local:
            raise LocalOperationNotSupportedError()
        _provider_call(lambda: self._remote.unsubscribe_artist(browse_id))


class ListeningHistoryService:
    def __init__(
        self,
        profile_context: ActiveMusicProfile,
        remote_library: MusicLibraryProvider,
    ) -> None:
        self._profile = profile_context
        self._remote = remote_library

    def add(self, video_id: str) -> int:
        if self._profile.is_local:
            raise LocalOperationNotSupportedError("authenticated profile required")
        _provider_call(lambda: self._remote.add_history_item(video_id))
        return 204


class PlaylistService:
    def __init__(
        self,
        profile_context: ActiveMusicProfile,
        remote_playlists: PlaylistProvider,
        remote_radio: SongRadioProvider,
        local_playlists: LocalMusicRepository,
        cache: Playlist,
        cache_settings: CacheSettings,
        audio_enricher: PlaylistAudioEnricher,
    ) -> None:
        self._profile = profile_context
        self._remote = remote_playlists
        self._remote_radio = remote_radio
        self._local = local_playlists
        self._cache = cache
        self._cache_settings = cache_settings
        self._audio = audio_enricher

    def get(self, playlist_id: str) -> dict[str, object]:
        profile_name = self._profile.name
        if self._profile.is_local:
            try:
                return _local_playlist_json(self._local.get_playlist(profile_name, playlist_id))
            except AccountConflictError:
                # Local profiles may still open public catalog playlists. This is
                # an anonymous read fallback; mutations always remain local.
                pass
        details = _provider_call(lambda: self._remote.get(playlist_id))
        enriched = _provider_call(
            lambda: self._audio.enrich(
                None if playlist_id == "LM" else playlist_id,
                details.tracks,
            )
        )
        return _remote_playlist_json(PlaylistDetails(details.title, details.thumbnail, enriched))

    def create(self, command: CreatePlaylist) -> CreatedPlaylist:
        profile_name = self._profile.name
        if self._profile.is_local:
            return self._local.create_playlist(profile_name, command)
        return _provider_call(lambda: self._remote.create(command))

    def edit(self, command: EditPlaylist) -> None:
        profile_name = self._profile.name
        if self._profile.is_local:
            self._local.edit_playlist(profile_name, command)
        else:
            _provider_call(lambda: self._remote.edit(command))
        self._cache.purge_playlist_cache(command.playlist_id, profile_name)

    def delete(self, playlist_id: str) -> None:
        profile_name = self._profile.name
        if self._profile.is_local:
            self._local.delete_playlist(profile_name, playlist_id)
        else:
            _provider_call(lambda: self._remote.delete(playlist_id))
        self._cache.purge_playlist_cache(playlist_id, profile_name)

    def add_items(self, command: AddPlaylistItems) -> None:
        profile_name = self._profile.name
        if self._profile.is_local:
            self._local.add_playlist_items(profile_name, command)
        else:
            _provider_call(lambda: self._remote.add_items(command))
        self._cache.purge_playlist_cache(command.playlist_id, profile_name)

    def remove_items(self, command: RemovePlaylistItems) -> None:
        profile_name = self._profile.name
        if self._profile.is_local:
            self._local.remove_playlist_items(profile_name, command)
        else:
            _provider_call(lambda: self._remote.remove_items(command))
        self._cache.purge_playlist_cache(command.playlist_id, profile_name)

    def radio(self, playlist_id: str, video_id: str = "") -> dict[str, object]:
        _ = self._profile.name
        radio = (
            _provider_call(lambda: self._remote_radio.song_radio(video_id))
            if playlist_id == "_"
            else _provider_call(lambda: self._remote.radio(playlist_id))
        )
        enriched = _provider_call(lambda: self._audio.enrich(None, radio.tracks))
        return {"tracks": [_radio_track_json(track) for track in enriched]}

    def stream(
        self,
        playlist_id: str,
        *,
        force_refresh: bool = False,
    ) -> Iterator[dict[str, object]]:
        profile_name = self._profile.name
        if self._profile.is_local:
            try:
                details = self._local.get_playlist(profile_name, playlist_id)
            except AccountConflictError:
                # Preserve public-playlist browsing for local profiles.
                pass
            else:
                tracks = [_local_track_json(track) for track in details.tracks]
                yield {
                    "type": "header",
                    "title": details.title,
                    "thumbnail": details.thumbnail,
                    "total": len(tracks),
                    "cached": True,
                }
                yield from _track_events(tracks)
                yield {"type": "done"}
                return

        if not force_refresh and self._cache_settings.enabled["playlists"]:
            cached = self._cached_playlist(playlist_id, profile_name)
            if cached is not None:
                yield from _cached_events(cached)
                return

        loading_message = (
            "Liked Songs werden abgerufen…" if playlist_id == "LM" else "Playlist wird abgerufen…"
        )
        yield {"type": "loading", "message": loading_message, "progress": 0}
        details = _provider_call(lambda: self._remote.get(playlist_id))
        yield {
            "type": "header",
            "title": details.title,
            "thumbnail": details.thumbnail,
            "total": len(details.tracks),
        }
        all_tracks: list[dict[str, object]] = []
        batches = _provider_call(
            lambda: self._audio.iter_enriched(
                None if playlist_id == "LM" else playlist_id,
                details.tracks,
                _RESOLUTION_BATCH_SIZE,
            )
        )
        try:
            for batch in batches:
                formatted = [_remote_track_json(track) for track in batch]
                all_tracks.extend(formatted)
                total = len(details.tracks)
                progress = min(100, round(len(all_tracks) / total * 100)) if total else 100
                yield {"type": "progress", "progress": progress}
                yield {"type": "tracks", "tracks": formatted}
        except ProviderAuthenticationError:
            raise AuthenticationRequiredError() from None
        except ProviderError:
            raise AccountProviderUnavailableError() from None
        cached_data: dict[str, object] = {
            "title": details.title,
            "thumbnail": details.thumbnail,
            "tracks": all_tracks,
        }
        # This line is reached only after the iterator completes. Generator close or
        # client disconnection therefore cannot commit a partial playlist.
        if self._cache_settings.enabled["playlists"]:
            self._cache.put(playlist_id, profile_name, cached_data)
            self._cache.save_playlist_disk(playlist_id, profile_name, cached_data)
        yield {"type": "done"}

    def _cached_playlist(self, playlist_id: str, profile_name: str) -> dict[str, object] | None:
        memory = self._cache.get_memory(playlist_id, profile_name)
        if isinstance(memory, dict):
            if _needs_audio_resolution(memory):
                self._cache.discard_memory(playlist_id, profile_name)
            else:
                return memory
        disk = self._cache.load_playlist_disk(playlist_id, profile_name)
        if isinstance(disk, dict) and not _needs_audio_resolution(disk):
            self._cache.put(playlist_id, profile_name, disk)
            return disk
        return None


def _provider_call[ResultT](operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except ProviderAuthenticationError:
        raise AuthenticationRequiredError() from None
    except ProviderUnavailableError:
        raise AccountProviderUnavailableError() from None
    except ProviderError:
        raise AccountProviderUnavailableError() from None


def liked_song_json(track: LikedSong) -> dict[str, object]:
    return {
        "type": "song",
        "videoId": track.video_id,
        "title": track.title,
        "artists": track.artists,
        "artistBrowseId": track.artist_browse_id,
        "artistLinks": [
            {"name": artist.name, "browseId": artist.browse_id} for artist in track.artist_links
        ],
        "album": track.album,
        "albumBrowseId": track.album_browse_id,
        "duration": track.duration,
        "thumbnail": track.thumbnail,
        "isExplicit": track.is_explicit,
    }


def local_liked_song_json(track: LikedSong) -> dict[str, object]:
    return {
        "videoId": track.video_id,
        "title": track.title,
        "artists": track.artists,
        "album": track.album,
        "thumbnail": track.thumbnail,
        "duration": track.duration,
    }


def _remote_playlist_json(details: PlaylistDetails) -> dict[str, object]:
    return {
        "title": details.title,
        "thumbnail": details.thumbnail,
        "tracks": [_remote_track_json(track) for track in details.tracks],
    }


def _local_playlist_json(details: PlaylistDetails) -> dict[str, object]:
    return {
        "title": details.title,
        "thumbnail": details.thumbnail,
        "tracks": [_local_track_json(track) for track in details.tracks],
    }


def _remote_track_json(track: PlaylistTrack) -> dict[str, object]:
    first_artist = track.artists[0] if track.artists else CatalogArtistReference("")
    return {
        "videoId": track.video_id,
        "setVideoId": track.set_video_id,
        "title": track.title,
        "artists": ", ".join(artist.name for artist in track.artists),
        "artistBrowseId": first_artist.browse_id,
        "artistLinks": [
            {"name": artist.name, "browseId": artist.browse_id} for artist in track.artists
        ],
        "album": track.album,
        "albumBrowseId": track.album_browse_id,
        "duration": track.duration,
        "thumbnail": track.thumbnails[0] if track.thumbnails else "",
        "hasVideoThumbnail": track.has_video_thumbnail,
        "isDetectedVideo": track.is_detected_video,
        "videoEvidence": list(track.video_evidence),
        "videoType": track.video_type,
        "thumbnailDimensions": list(track.thumbnail_dimensions),
        "isExplicit": track.is_explicit,
    }


def _local_track_json(track: PlaylistTrack) -> dict[str, object]:
    return {
        "videoId": track.video_id,
        "setVideoId": track.set_video_id,
        "title": track.title,
        "artists": ", ".join(artist.name for artist in track.artists),
        "album": track.album,
        "thumbnail": track.thumbnails[0] if track.thumbnails else "",
        "duration": track.duration,
    }


def _radio_track_json(track: PlaylistTrack) -> dict[str, object]:
    return {
        "videoId": track.video_id,
        "title": track.title,
        "artists": ", ".join(artist.name for artist in track.artists),
        "album": track.album,
        "thumbnail": track.thumbnails[0] if track.thumbnails else "",
        "duration": track.duration,
        "isExplicit": track.is_explicit,
    }


def _track_events(tracks: list[dict[str, object]]) -> Iterator[dict[str, object]]:
    for index in range(0, len(tracks), _TRANSFER_CHUNK_SIZE):
        yield {"type": "tracks", "tracks": tracks[index : index + _TRANSFER_CHUNK_SIZE]}


def _cached_events(data: dict[str, object]) -> Iterator[dict[str, object]]:
    tracks = data.get("tracks")
    normalized_tracks = tracks if isinstance(tracks, list) else []
    yield {
        "type": "header",
        "title": data.get("title", ""),
        "thumbnail": data.get("thumbnail", ""),
        "total": len(normalized_tracks),
        "cached": True,
    }
    yield from _track_events(normalized_tracks)
    yield {"type": "done"}


def _needs_audio_resolution(data: Mapping[str, object]) -> bool:
    tracks = data.get("tracks")
    if not isinstance(tracks, list):
        return False
    return any(
        isinstance(track, Mapping)
        and (track.get("isDetectedVideo") is True or "isExplicit" not in track)
        for track in tracks
    )
