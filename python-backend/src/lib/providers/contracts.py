"""Narrow structural interfaces implemented by external provider adapters."""

from typing import Protocol

from .models import (
    AddPlaylistItems,
    CatalogAlbum,
    CatalogSearchQuery,
    CatalogSearchResult,
    CreatedPlaylist,
    CreatePlaylist,
    EditPlaylist,
    LibraryAlbum,
    LibraryArtist,
    LibraryPlaylist,
    LikedSongsPage,
    LikedSongsQuery,
    PlaylistDetails,
    PlaylistRadio,
    RemovePlaylistItems,
    SongCredits,
    SongRating,
    SongStatistics,
)


class MusicCatalogProvider(Protocol):
    """Read the searchable and browsable parts of a music catalog."""

    def search(self, query: CatalogSearchQuery) -> list[CatalogSearchResult]: ...

    def suggestions(self, query: str, limit: int) -> list[str]: ...

    def album(self, browse_id: str) -> CatalogAlbum: ...


# Kept as a source-compatible name for capability clients introduced before the
# catalog contract gained suggestions and album browsing.
CatalogProvider = MusicCatalogProvider


class MusicLibraryProvider(Protocol):
    """Read and mutate an authenticated music library."""

    def albums(self) -> tuple[LibraryAlbum, ...]: ...

    def artists(self) -> tuple[LibraryArtist, ...]: ...

    def playlists(self) -> tuple[LibraryPlaylist, ...]: ...

    def liked_songs(self, query: LikedSongsQuery) -> LikedSongsPage: ...

    def liked_song_ids(self) -> frozenset[str]: ...

    def rate_song(self, video_id: str, rating: SongRating) -> None: ...

    def subscribe_artist(self, browse_id: str) -> None: ...

    def unsubscribe_artist(self, browse_id: str) -> None: ...

    def add_history_item(self, video_id: str) -> None: ...


class PlaylistProvider(Protocol):
    """Read and mutate playlists without exposing provider payloads."""

    def get(self, playlist_id: str) -> PlaylistDetails: ...

    def create(self, command: CreatePlaylist) -> CreatedPlaylist: ...

    def edit(self, command: EditPlaylist) -> None: ...

    def delete(self, playlist_id: str) -> None: ...

    def add_items(self, command: AddPlaylistItems) -> None: ...

    def remove_items(self, command: RemovePlaylistItems) -> None: ...

    def radio(self, playlist_id: str) -> PlaylistRadio: ...


# Source-compatible aliases for integrations created before the account-scoped
# contracts were introduced.
LibraryProvider = MusicLibraryProvider
PlaylistsProvider = PlaylistProvider


class SongStatisticsProvider(Protocol):
    """Read normalized song engagement statistics."""

    def get_statistics(self, video_id: str) -> SongStatistics: ...


class SongCreditsProvider(Protocol):
    def get_credits(self, video_id: str) -> SongCredits: ...
