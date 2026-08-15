from collections.abc import Callable
from typing import cast

import pytest
from src.lib.providers import (
    CatalogAlbum,
    CatalogArtistReference,
    CatalogProvider,
    CatalogSearchFilter,
    CatalogSearchQuery,
    CatalogSearchResult,
    CatalogSong,
    DuplicateProviderNamespaceError,
    LibrarySongState,
    MissingProviderNamespaceError,
    MusicLibraryProvider,
    PlaylistProvider,
    PlaylistReference,
    ProviderCollection,
    ProviderResponseError,
    SongStatistics,
    SongStatisticsCapabilities,
    SongStatisticsProvider,
    YoutubeCapabilities,
    translate_provider_errors,
)


class FakeCatalog:
    def __init__(self) -> None:
        self.search_calls = 0

    def search(self, query: CatalogSearchQuery) -> list[CatalogSearchResult]:
        self.search_calls += 1
        return [
            CatalogSong(
                video_id="video-id",
                title=query.text,
                artists=(CatalogArtistReference("Artist"),),
            )
        ]

    def suggestions(self, query: str, limit: int) -> list[str]:
        return [query]

    def album(self, browse_id: str) -> CatalogAlbum:
        return CatalogAlbum(browse_id, "Album", (), "", "", ())


class FakeLibrary:
    def like_song(self, video_id: str) -> LibrarySongState:
        return LibrarySongState(video_id=video_id, liked=True)


class FakePlaylists:
    def create(self, title: str, *, description: str = "") -> PlaylistReference:
        return PlaylistReference(playlist_id="playlist-id", title=title)


class FakeSongStatistics:
    def get_statistics(self, video_id: str) -> SongStatistics:
        return SongStatistics(views=100, likes=20, dislikes=1)


def youtube_capabilities(catalog: CatalogProvider | None = None) -> YoutubeCapabilities:
    return YoutubeCapabilities(
        catalog=catalog or FakeCatalog(),
        library=cast("MusicLibraryProvider", FakeLibrary()),
        playlists=cast("PlaylistProvider", FakePlaylists()),
    )


class ProviderCompositionTests:
    def test_capability_bundle_can_be_registered_and_resolved(self) -> None:
        catalog = FakeCatalog()
        providers = ProviderCollection()

        providers.use(youtube_capabilities(catalog))

        assert providers.youtube.catalog is catalog
        query = CatalogSearchQuery("Song", CatalogSearchFilter.SONGS)
        result = providers.youtube.catalog.search(query)[0]
        assert isinstance(result, CatalogSong)
        assert result.video_id == "video-id"

    def test_duplicate_namespace_is_rejected_during_registration(self) -> None:
        providers = ProviderCollection()
        providers.use(youtube_capabilities())

        with pytest.raises(
            DuplicateProviderNamespaceError,
            match="Provider namespace 'youtube' is already registered",
        ):
            providers.use(youtube_capabilities())

    def test_missing_namespace_has_a_clear_composition_error(self) -> None:
        providers = ProviderCollection()

        with pytest.raises(
            MissingProviderNamespaceError,
            match="Required provider namespace 'song_statistics' was not registered",
        ):
            _ = providers.song_statistics

    def test_protocol_compatible_fake_can_replace_a_capability(self) -> None:
        fake: SongStatisticsProvider = FakeSongStatistics()
        providers = ProviderCollection()
        providers.use(SongStatisticsCapabilities(provider=fake))

        assert providers.song_statistics is fake
        assert providers.song_statistics.get_statistics("video-id") == SongStatistics(
            views=100,
            likes=20,
            dislikes=1,
        )

    def test_vendor_failure_is_converted_without_sensitive_details(self) -> None:
        class VendorResponseError(Exception):
            pass

        def fail() -> None:
            raise VendorResponseError("Authorization: secret-token; raw={...}")

        def call_provider(operation: Callable[[], None]) -> None:
            with translate_provider_errors(VendorResponseError):
                operation()

        with pytest.raises(ProviderResponseError) as raised:
            call_provider(fail)

        assert str(raised.value) == "Provider returned an invalid response."
        assert raised.value.__cause__ is None

    def test_registration_performs_no_capability_io(self) -> None:
        catalog = FakeCatalog()
        providers = ProviderCollection()

        providers.use(youtube_capabilities(catalog))

        assert catalog.search_calls == 0
