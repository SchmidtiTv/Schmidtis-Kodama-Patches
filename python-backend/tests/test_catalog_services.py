from src.lib.music import AlbumDetailsService, SearchService
from src.lib.providers import (
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

ARTIST = CatalogArtistReference("Artist", "artist-id")
ALBUM = CatalogAlbum(
    browse_id="album-id",
    title="Album",
    artists=(ARTIST,),
    year="2026",
    thumbnail="album-image",
    tracks=(
        CatalogTrack(
            video_id="song-id",
            title="Song",
            artists=(ARTIST,),
            duration="3:04",
            is_explicit=True,
        ),
    ),
)


class FakeCatalog:
    def __init__(self) -> None:
        self.results: list[CatalogSearchResult] = []
        self.suggestion_results: list[str] = []
        self.album_result = ALBUM
        self.search_calls: list[CatalogSearchQuery] = []
        self.suggestion_calls: list[tuple[str, int]] = []
        self.album_calls: list[str] = []

    def search(self, query: CatalogSearchQuery) -> list[CatalogSearchResult]:
        self.search_calls.append(query)
        return self.results

    def suggestions(self, query: str, limit: int) -> list[str]:
        self.suggestion_calls.append((query, limit))
        return self.suggestion_results

    def album(self, browse_id: str) -> CatalogAlbum:
        self.album_calls.append(browse_id)
        return self.album_result


class FakeAlbumCache:
    def __init__(self, cached: dict[str, object] | None = None) -> None:
        self.cached = cached
        self.loads: list[str] = []
        self.saves: list[tuple[str, dict[str, object]]] = []

    def load_album_disk(self, browse_id: str) -> dict[str, object] | None:
        self.loads.append(browse_id)
        return self.cached

    def save_album_disk(self, browse_id: str, data: dict[str, object]) -> None:
        self.saves.append((browse_id, data))


class FakeCacheSettings:
    def __init__(self, albums: bool) -> None:
        self.enabled = {"albums": albums}


def test_search_service_preserves_all_successful_result_shapes() -> None:
    catalog = FakeCatalog()
    catalog.results = [
        CatalogSong(
            video_id="song-id",
            title="Song",
            artists=(ARTIST,),
            album="Album",
            album_browse_id="album-id",
            duration="3:04",
            thumbnail="song-image",
            is_explicit=True,
        ),
        CatalogArtist("artist-id", "Artist", "12K", "artist-image"),
        CatalogAlbumSummary("album-id", "Album", (ARTIST,), "2026", "album-image"),
        CatalogPlaylist("playlist-id", "VLplaylist-id", "Playlist", "Curator", "pl-image"),
    ]

    result = SearchService(catalog).search(CatalogSearchQuery("query", CatalogSearchFilter.ALL))

    assert result == {
        "results": [
            {
                "type": "song",
                "videoId": "song-id",
                "title": "Song",
                "artists": "Artist",
                "artistBrowseId": "artist-id",
                "artistLinks": [{"name": "Artist", "browseId": "artist-id"}],
                "album": "Album",
                "albumBrowseId": "album-id",
                "duration": "3:04",
                "thumbnail": "song-image",
                "isExplicit": True,
            },
            {
                "type": "artist",
                "browseId": "artist-id",
                "title": "Artist",
                "subtitle": "12K",
                "thumbnail": "artist-image",
            },
            {
                "type": "album",
                "browseId": "album-id",
                "title": "Album",
                "artists": "Artist",
                "year": "2026",
                "thumbnail": "album-image",
            },
            {
                "type": "playlist",
                "playlistId": "playlist-id",
                "browseId": "VLplaylist-id",
                "title": "Playlist",
                "subtitle": "Curator",
                "thumbnail": "pl-image",
            },
        ]
    }


def test_search_service_short_circuits_empty_search_and_deduplicates_suggestions() -> None:
    catalog = FakeCatalog()
    service = SearchService(catalog)

    assert service.search(CatalogSearchQuery("", CatalogSearchFilter.SONGS)) == {"results": []}
    assert catalog.search_calls == []
    assert service.suggestions(" x ") == {"suggestions": []}
    assert catalog.suggestion_calls == []

    catalog.suggestion_results = [" Song ", "song", "SONG", "Artist", "  "]
    assert service.suggestions(" so ") == {"suggestions": ["Song", "Artist"]}
    assert catalog.suggestion_calls == [("so", 6)]


def test_album_service_cache_hit_returns_cached_response_without_provider_io() -> None:
    cached: dict[str, object] = {"title": "Cached", "tracks": []}
    catalog = FakeCatalog()
    cache = FakeAlbumCache(cached)

    result = AlbumDetailsService(catalog, cache, FakeCacheSettings(True)).get("album-id")

    assert result is cached
    assert cache.loads == ["album-id"]
    assert catalog.album_calls == []
    assert cache.saves == []


def test_album_service_cache_miss_formats_and_persists_existing_response_shape() -> None:
    catalog = FakeCatalog()
    cache = FakeAlbumCache()

    result = AlbumDetailsService(catalog, cache, FakeCacheSettings(True)).get("album-id")

    assert result == {
        "title": "Album",
        "artists": "Artist",
        "artistBrowseId": "artist-id",
        "year": "2026",
        "thumbnail": "album-image",
        "tracks": [
            {
                "videoId": "song-id",
                "title": "Song",
                "artists": "Artist",
                "artistBrowseId": "artist-id",
                "artistLinks": [{"name": "Artist", "browseId": "artist-id"}],
                "album": "Album",
                "duration": "3:04",
                "thumbnail": "album-image",
                "isExplicit": True,
            }
        ],
    }
    assert catalog.album_calls == ["album-id"]
    assert cache.saves == [("album-id", result)]


def test_album_service_disabled_cache_skips_lookup_and_persistence() -> None:
    catalog = FakeCatalog()
    cache = FakeAlbumCache({"title": "Cached"})

    AlbumDetailsService(catalog, cache, FakeCacheSettings(False)).get("album-id")

    assert cache.loads == []
    assert cache.saves == []
    assert catalog.album_calls == ["album-id"]


def test_album_service_forced_refresh_bypasses_lookup_but_updates_enabled_cache() -> None:
    catalog = FakeCatalog()
    cache = FakeAlbumCache({"title": "Cached"})

    result = AlbumDetailsService(catalog, cache, FakeCacheSettings(True)).get(
        "album-id", force_refresh=True
    )

    assert cache.loads == []
    assert catalog.album_calls == ["album-id"]
    assert cache.saves == [("album-id", result)]
