from typing import cast

import pytest
import requests
from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.providers import (
    CatalogAlbumSummary,
    CatalogArtist,
    CatalogPlaylist,
    CatalogSearchFilter,
    CatalogSearchQuery,
    CatalogSong,
    ProviderAuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
    YoutubeMusicCatalogProvider,
)


class FakeCatalogClient:
    def __init__(self) -> None:
        self.search_result: object = []
        self.album_result: object = {}
        self.search_calls: list[tuple[object, object, object]] = []
        self.search_error: Exception | None = None
        self.album_error: Exception | None = None

    def search(self, query: object, filter: object = "songs", limit: object = 20) -> object:
        self.search_calls.append((query, filter, limit))
        if self.search_error is not None:
            raise self.search_error
        return self.search_result

    def get_album(self, browse_id: object) -> object:
        if self.album_error is not None:
            raise self.album_error
        return self.album_result


class FakeCatalogSession:
    def __init__(self) -> None:
        self.active = FakeCatalogClient()
        self.system = FakeCatalogClient()
        self.auth_error: Exception | None = None

    def get_active_client(self) -> FakeCatalogClient:
        if self.auth_error is not None:
            raise self.auth_error
        return self.active

    def get_system_client(self) -> FakeCatalogClient:
        return self.system


def provider(session: FakeCatalogSession) -> YoutubeMusicCatalogProvider:
    return YoutubeMusicCatalogProvider(cast("YoutubeMusicSession", session))


@pytest.mark.parametrize("search_filter", list(CatalogSearchFilter))
def test_every_public_filter_is_forwarded_to_ytmusic(
    search_filter: CatalogSearchFilter,
) -> None:
    session = FakeCatalogSession()

    provider(session).search(CatalogSearchQuery("query", search_filter, limit=13))

    expected_filter = None if search_filter is CatalogSearchFilter.ALL else search_filter.value
    assert session.active.search_calls == [("query", expected_filter, 13)]


def test_search_normalizes_supported_results_and_drops_malformed_entries() -> None:
    session = FakeCatalogSession()
    session.active.search_result = [
        {
            "resultType": "song",
            "videoId": "song-id",
            "title": "Song",
            "artists": [
                {"name": "Song", "id": None},
                {"name": "Artist", "id": "artist-id"},
            ],
            "album": {"name": "Album", "id": "album-id"},
            "duration": "3:04",
            "isExplicit": True,
            "thumbnails": [
                {"url": "small", "width": 100},
                {"url": "right-size", "width": 300},
            ],
        },
        {
            "resultType": "artist",
            "subscribers": "12K",
            "artists": [{"name": "Top Artist", "id": "top-id"}],
            "thumbnails": [{"url": "artist-image"}],
        },
        {
            "resultType": "album",
            "browseId": "album-id",
            "title": "Album",
            "artist": "Fallback Artist",
            "year": "2026",
            "thumbnails": [{"url": "album-image"}],
        },
        {
            "resultType": "playlist",
            "browseId": "VLplaylist-id",
            "title": "Playlist",
            "author": "Curator",
            "thumbnails": [{"url": "playlist-image"}],
        },
        {"resultType": "song", "title": "No video id"},
        {"resultType": "artist", "title": "No browse id"},
        {"resultType": "album", "browseId": "id-without-title"},
        {"resultType": "playlist", "title": "No playlist id"},
        {"resultType": "episode", "videoId": "episode-id", "title": "Episode"},
        "not a mapping",
    ]

    results = provider(session).search(CatalogSearchQuery("anything", CatalogSearchFilter.ALL))

    assert len(results) == 4
    song = cast("CatalogSong", results[0])
    assert isinstance(song, CatalogSong)
    assert song.video_id == "song-id"
    assert [(artist.name, artist.browse_id) for artist in song.artists] == [("Artist", "artist-id")]
    assert (song.album, song.album_browse_id, song.thumbnail, song.is_explicit) == (
        "Album",
        "album-id",
        "right-size",
        True,
    )
    artist = cast("CatalogArtist", results[1])
    assert isinstance(artist, CatalogArtist)
    assert (artist.browse_id, artist.title, artist.subscribers) == (
        "top-id",
        "Top Artist",
        "12K",
    )
    album = cast("CatalogAlbumSummary", results[2])
    assert isinstance(album, CatalogAlbumSummary)
    assert [(artist.name, artist.browse_id) for artist in album.artists] == [
        ("Fallback Artist", "")
    ]
    playlist = cast("CatalogPlaylist", results[3])
    assert isinstance(playlist, CatalogPlaylist)
    assert (playlist.playlist_id, playlist.browse_id) == (
        "playlist-id",
        "VLplaylist-id",
    )


def test_suggestions_keep_only_string_titles_for_service_level_deduplication() -> None:
    session = FakeCatalogSession()
    session.active.search_result = [
        {"title": "Song"},
        {"title": "song"},
        {"title": ""},
        {"title": 42},
        None,
    ]

    assert provider(session).suggestions("so", 6) == ["Song", "song"]
    assert session.active.search_calls == [("so", None, 6)]


def test_album_normalizes_artists_excludes_unplayable_tracks_and_selects_audio_version() -> None:
    session = FakeCatalogSession()
    session.active.album_result = {
        "title": "Album",
        "artists": [{"name": "Album Artist", "id": "album-artist-id"}],
        "year": "2026",
        "thumbnails": [{"url": "album-image"}],
        "tracks": [
            {
                "videoId": "video-id",
                "title": "Song (Official Music Video)",
                "artists": [{"name": "Album Artist", "id": "album-artist-id"}],
                "duration": "3:00",
                "videoType": "MUSIC_VIDEO_TYPE_OMV",
            },
            {"title": "No video id"},
            {
                "videoId": "second-id",
                "title": "Second Song",
                "duration": "2:00",
                "isExplicit": True,
            },
        ],
    }
    session.system.search_result = [
        {
            "resultType": "song",
            "videoId": "audio-id",
            "title": "Song",
            "artists": [{"name": "Album Artist", "id": "album-artist-id"}],
            "duration": "3:00",
            "videoType": "MUSIC_VIDEO_TYPE_ATV",
        }
    ]

    album = provider(session).album("browse-id")

    assert (album.browse_id, album.title, album.year, album.thumbnail) == (
        "browse-id",
        "Album",
        "2026",
        "album-image",
    )
    assert [(artist.name, artist.browse_id) for artist in album.artists] == [
        ("Album Artist", "album-artist-id")
    ]
    assert [track.video_id for track in album.tracks] == ["audio-id", "second-id"]
    assert album.tracks[1].artists == album.artists
    assert album.tracks[1].is_explicit is True
    assert session.system.search_calls[0][1:] == ("songs", 10)


def test_authentication_and_upstream_failures_are_translated() -> None:
    session = FakeCatalogSession()
    session.auth_error = RuntimeError("secret auth response")
    with pytest.raises(ProviderAuthenticationError, match="authentication failed"):
        provider(session).search(CatalogSearchQuery("query", CatalogSearchFilter.SONGS))

    session.auth_error = None
    session.active.search_error = RuntimeError("raw parser payload")
    with pytest.raises(ProviderResponseError, match="invalid response"):
        provider(session).search(CatalogSearchQuery("query", CatalogSearchFilter.SONGS))

    session.active.search_error = requests.ConnectionError("network details")
    with pytest.raises(ProviderUnavailableError, match="unavailable"):
        provider(session).search(CatalogSearchQuery("query", CatalogSearchFilter.SONGS))

    session.active.search_error = None
    session.active.album_result = []
    with pytest.raises(ProviderResponseError, match="invalid response"):
        provider(session).album("album-id")
