from collections.abc import Callable, Generator, Iterator
from typing import cast

import pytest
from src.lib.accounts import (
    AccountProviderUnavailableError,
    AccountValidationError,
    ArtistSubscriptionService,
    AuthenticationRequiredError,
    LibraryService,
    LikedSongsService,
    ListeningHistoryService,
    LocalOperationNotSupportedError,
    PlaylistService,
    SongRatingService,
    parse_add_playlist_items,
    parse_create_playlist,
    parse_edit_playlist,
    parse_rating,
    parse_remove_playlist_items,
)
from src.lib.accounts.context import ActiveMusicProfile
from src.lib.accounts.repositories import LocalMusicRepository
from src.lib.accounts.services import PlaylistAudioEnricher, SongRadioProvider
from src.lib.music.playlist import Playlist
from src.lib.providers import (
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
    MusicLibraryProvider,
    PlaylistDetails,
    PlaylistProvider,
    PlaylistRadio,
    PlaylistTrack,
    ProviderAuthenticationError,
    ProviderUnavailableError,
    RemovePlaylistItems,
    SongRating,
)
from src.lib.runtime.cache import CacheSettings


class MutableProfile:
    def __init__(self, name: str | None = "remote", is_local: bool = False) -> None:
        self.current_name = name
        self.local = is_local

    @property
    def name(self) -> str:
        if self.current_name is None:
            raise AuthenticationRequiredError()
        return self.current_name

    @property
    def is_local(self) -> bool:
        _ = self.name
        return self.local


class RecordingLibrary:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.error: Exception | None = None

    def _record(self, value: object) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append(value)

    def albums(self) -> tuple[LibraryAlbum, ...]:
        self._record("albums")
        return (LibraryAlbum("album", "Album", "Artist", "2026", "image"),)

    def artists(self) -> tuple[LibraryArtist, ...]:
        self._record("artists")
        return (LibraryArtist("artist", "Artist", "10", "image"),)

    def playlists(self) -> tuple[LibraryPlaylist, ...]:
        self._record("playlists")
        return (LibraryPlaylist("playlist", "Playlist", "1", "image"),)

    def liked_songs(self, query: LikedSongsQuery) -> LikedSongsPage:
        self._record(("liked", query))
        return LikedSongsPage((_liked_song(),), 1, query.offset, False)

    def liked_song_ids(self) -> frozenset[str]:
        self._record("liked_ids")
        return frozenset({"video"})

    def rate_song(self, video_id: str, rating: SongRating) -> None:
        self._record(("rate", video_id, rating))

    def subscribe_artist(self, browse_id: str) -> None:
        self._record(("subscribe", browse_id))

    def unsubscribe_artist(self, browse_id: str) -> None:
        self._record(("unsubscribe", browse_id))

    def add_history_item(self, video_id: str) -> None:
        self._record(("history", video_id))


class RecordingLocalRepository:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def library_playlists(self, profile: str) -> tuple[LibraryPlaylist, ...]:
        self.calls.append(("playlists", profile))
        return (LibraryPlaylist("local", "Local", "0", "", ""),)

    def liked_songs(self, profile: str) -> tuple[LikedSong, ...]:
        self.calls.append(("liked", profile))
        return (_liked_song(),)

    def liked_song_ids(self, profile: str) -> frozenset[str]:
        self.calls.append(("liked_ids", profile))
        return frozenset({"local-video"})

    def rate_song(
        self,
        profile: str,
        video_id: str,
        rating: SongRating,
        metadata: dict[str, str],
    ) -> None:
        self.calls.append(("rate", profile, video_id, rating, metadata))

    def get_playlist(self, profile: str, playlist_id: str) -> PlaylistDetails:
        self.calls.append(("get", profile, playlist_id))
        return PlaylistDetails("Local", "", (_track("local-video"),))

    def create_playlist(self, profile: str, command: CreatePlaylist) -> CreatedPlaylist:
        self.calls.append(("create", profile, command))
        return CreatedPlaylist("local-created")

    def edit_playlist(self, profile: str, command: EditPlaylist) -> None:
        self.calls.append(("edit", profile, command))

    def delete_playlist(self, profile: str, playlist_id: str) -> None:
        self.calls.append(("delete", profile, playlist_id))

    def add_playlist_items(self, profile: str, command: AddPlaylistItems) -> None:
        self.calls.append(("add", profile, command))

    def remove_playlist_items(self, profile: str, command: RemovePlaylistItems) -> None:
        self.calls.append(("remove", profile, command))


class RecordingPlaylists:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.error: Exception | None = None

    def _record(self, value: object) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append(value)

    def get(self, playlist_id: str) -> PlaylistDetails:
        self._record(("get", playlist_id))
        return PlaylistDetails("Remote", "image", (_track(),))

    def create(self, command: CreatePlaylist) -> CreatedPlaylist:
        self._record(("create", command))
        return CreatedPlaylist("created")

    def edit(self, command: EditPlaylist) -> None:
        self._record(("edit", command))

    def delete(self, playlist_id: str) -> None:
        self._record(("delete", playlist_id))

    def add_items(self, command: AddPlaylistItems) -> None:
        self._record(("add", command))

    def remove_items(self, command: RemovePlaylistItems) -> None:
        self._record(("remove", command))

    def radio(self, playlist_id: str) -> PlaylistRadio:
        self._record(("radio", playlist_id))
        return PlaylistRadio((_track(),))

    def song_radio(self, video_id: str) -> PlaylistRadio:
        self._record(("song_radio", video_id))
        return PlaylistRadio((_track(),))


class PassthroughEnricher:
    def enrich(
        self, playlist_id: str | None, tracks: tuple[PlaylistTrack, ...]
    ) -> tuple[PlaylistTrack, ...]:
        return tracks

    def iter_enriched(
        self,
        playlist_id: str | None,
        tracks: tuple[PlaylistTrack, ...],
        batch_size: int,
    ) -> Iterator[tuple[PlaylistTrack, ...]]:
        yield tracks

    def enrich_liked(self, tracks: tuple[LikedSong, ...]) -> tuple[LikedSong, ...]:
        return tracks


class RecordingCache:
    def __init__(self) -> None:
        self.memory: dict[tuple[str, str], dict[str, object]] = {}
        self.purged: list[tuple[str, str | None]] = []
        self.saved: list[tuple[str, str | None]] = []

    def purge_playlist_cache(self, playlist_id: str, profile: str | None) -> None:
        self.purged.append((playlist_id, profile))

    def get_memory(self, playlist_id: str, profile: str | None) -> dict[str, object] | None:
        return self.memory.get((profile or "default", playlist_id))

    def discard_memory(self, playlist_id: str, profile: str | None) -> None:
        self.memory.pop((profile or "default", playlist_id), None)

    def load_playlist_disk(self, playlist_id: str, profile: str | None) -> dict[str, object] | None:
        return None

    def put(self, playlist_id: str, profile: str | None, data: dict[str, object]) -> None:
        self.memory[(profile or "default", playlist_id)] = data

    def save_playlist_disk(
        self, playlist_id: str, profile: str | None, data: dict[str, object]
    ) -> None:
        self.saved.append((playlist_id, profile))


def _liked_song() -> LikedSong:
    return LikedSong("video", "Song", "Artist", "artist", (), "Album", "album", "3:00", "", False)


def _track(video_id: str = "video") -> PlaylistTrack:
    return PlaylistTrack(
        video_id,
        "set-video",
        "Song",
        (CatalogArtistReference("Artist", "artist"),),
        "Album",
        "album",
        "3:00",
        ("image",),
    )


def _services(
    profile: MutableProfile | None = None,
) -> tuple[
    MutableProfile,
    RecordingLibrary,
    RecordingLocalRepository,
    RecordingPlaylists,
    RecordingCache,
    PlaylistService,
]:
    profile = profile or MutableProfile()
    remote_library = RecordingLibrary()
    local = RecordingLocalRepository()
    remote_playlists = RecordingPlaylists()
    cache = RecordingCache()
    playlist_service = PlaylistService(
        cast("ActiveMusicProfile", profile),
        cast("PlaylistProvider", remote_playlists),
        cast("SongRadioProvider", remote_playlists),
        cast("LocalMusicRepository", local),
        cast("Playlist", cache),
        CacheSettings(defaults={"playlists": True}),
        cast("PlaylistAudioEnricher", PassthroughEnricher()),
    )
    return profile, remote_library, local, remote_playlists, cache, playlist_service


def test_every_account_service_uses_the_remote_capability_for_a_remote_profile() -> None:
    profile, remote, local, _, _, playlists = _services()
    context = cast("ActiveMusicProfile", profile)
    repository = cast("LocalMusicRepository", local)
    provider = cast("MusicLibraryProvider", remote)

    assert LibraryService(context, provider, repository).albums()[0].browse_id == "album"
    assert LikedSongsService(
        context,
        provider,
        repository,
        cast("PlaylistAudioEnricher", PassthroughEnricher()),
    ).ids() == frozenset({"video"})
    SongRatingService(context, provider, repository).rate(
        "video", SongRating.INDIFFERENT, _metadata()
    )
    subscriptions = ArtistSubscriptionService(context, provider)
    subscriptions.subscribe("artist")
    subscriptions.unsubscribe("artist")
    assert ListeningHistoryService(context, provider).add("video") == 204
    assert playlists.get("playlist")["title"] == "Remote"

    assert local.calls == []
    assert remote.calls == [
        "albums",
        "liked_ids",
        ("rate", "video", SongRating.INDIFFERENT),
        ("subscribe", "artist"),
        ("unsubscribe", "artist"),
        ("history", "video"),
    ]


def test_local_services_never_call_remote_providers_and_rating_reset_deletes_locally() -> None:
    profile, remote, local, remote_playlists, _, playlists = _services(
        MutableProfile("local", True)
    )
    context = cast("ActiveMusicProfile", profile)
    repository = cast("LocalMusicRepository", local)
    provider = cast("MusicLibraryProvider", remote)

    assert LibraryService(context, provider, repository).albums() == ()
    assert LibraryService(context, provider, repository).playlists()[0].playlist_id == "local"
    assert (
        LikedSongsService(
            context,
            provider,
            repository,
            cast("PlaylistAudioEnricher", PassthroughEnricher()),
        )
        .songs(LikedSongsQuery())
        .total
        is None
    )
    SongRatingService(context, provider, repository).rate(
        "video", SongRating.INDIFFERENT, _metadata()
    )
    assert playlists.get("playlist")["title"] == "Local"

    assert remote.calls == []
    assert remote_playlists.calls == []
    assert ("rate", "local", "video", SongRating.INDIFFERENT, _metadata()) in local.calls


def test_profile_switching_changes_the_repository_path_on_the_next_call() -> None:
    profile, remote, local, _, _, _ = _services()
    service = LibraryService(
        cast("ActiveMusicProfile", profile),
        cast("MusicLibraryProvider", remote),
        cast("LocalMusicRepository", local),
    )

    assert service.playlists()[0].playlist_id == "playlist"
    profile.current_name = "local"
    profile.local = True
    assert service.playlists()[0].playlist_id == "local"

    assert remote.calls == ["playlists"]
    assert local.calls == [("playlists", "local")]


def test_missing_profile_and_provider_failures_become_safe_application_errors() -> None:
    profile, remote, local, _, _, _ = _services(MutableProfile(None))
    service = LibraryService(
        cast("ActiveMusicProfile", profile),
        cast("MusicLibraryProvider", remote),
        cast("LocalMusicRepository", local),
    )
    with pytest.raises(AuthenticationRequiredError):
        service.albums()

    profile.current_name = "remote"
    remote.error = ProviderAuthenticationError()
    with pytest.raises(AuthenticationRequiredError):
        service.albums()
    remote.error = ProviderUnavailableError()
    with pytest.raises(AccountProviderUnavailableError):
        service.albums()


def test_local_account_only_operations_are_rejected_without_remote_calls() -> None:
    profile, remote, _, _, _, _ = _services(MutableProfile("local", True))
    context = cast("ActiveMusicProfile", profile)
    provider = cast("MusicLibraryProvider", remote)

    with pytest.raises(LocalOperationNotSupportedError):
        ArtistSubscriptionService(context, provider).subscribe("artist")
    with pytest.raises(LocalOperationNotSupportedError):
        ListeningHistoryService(context, provider).add("video")
    assert remote.calls == []


def test_playlist_cache_changes_only_after_successful_mutations() -> None:
    _, _, _, remote, cache, service = _services()
    command = parse_add_playlist_items("playlist", {"videoIds": ["video"]})

    remote.error = ProviderUnavailableError()
    with pytest.raises(AccountProviderUnavailableError):
        service.add_items(command)
    assert cache.purged == []

    remote.error = None
    service.add_items(command)
    assert cache.purged == [("playlist", "remote")]


def test_closing_playlist_stream_before_completion_does_not_commit_cache() -> None:
    _, _, _, _, cache, service = _services()
    stream = cast(
        "Generator[dict[str, object], None, None]",
        service.stream("playlist", force_refresh=True),
    )

    assert next(stream)["type"] == "loading"
    assert next(stream)["type"] == "header"
    assert next(stream)["type"] == "progress"
    stream.close()

    assert cache.memory == {}
    assert cache.saved == []


@pytest.mark.parametrize(
    "operation",
    [
        lambda: parse_rating("LOVE"),
        lambda: parse_create_playlist({"title": "", "privacyStatus": "PRIVATE"}),
        lambda: parse_create_playlist({"title": "Title", "privacyStatus": "FRIENDS"}),
        lambda: parse_add_playlist_items("playlist", {"videoIds": "video"}),
        lambda: parse_add_playlist_items("playlist", {"videoIds": [1]}),
        lambda: parse_add_playlist_items("playlist", {"videoIds": ["video", "video"]}),
        lambda: parse_add_playlist_items(
            "playlist",
            {"videoIds": ["video"], "tracks": [{"videoId": "different"}]},
        ),
        lambda: parse_add_playlist_items(
            "playlist", {"videoIds": [f"video-{index}" for index in range(501)]}
        ),
        lambda: parse_remove_playlist_items("playlist", {"videos": [{}]}),
        lambda: parse_remove_playlist_items(
            "playlist",
            {
                "videos": [
                    {"videoId": "video", "setVideoId": "set"},
                    {"videoId": "video", "setVideoId": "set"},
                ]
            },
        ),
        lambda: parse_edit_playlist("playlist", {"title": " "}),
    ],
)
def test_mutation_commands_reject_invalid_payloads(operation: Callable[[], object]) -> None:
    with pytest.raises(AccountValidationError):
        operation()


def _metadata() -> dict[str, str]:
    return {field: "" for field in ("title", "artists", "album", "thumbnail", "duration")}
