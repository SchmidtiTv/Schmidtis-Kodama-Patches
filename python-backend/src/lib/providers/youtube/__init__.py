"""YouTube Music provider capabilities."""

from .catalog import YoutubeMusicCatalogProvider
from .credits import YoutubeSongCreditsProvider
from .library import YoutubeMusicLibraryProvider
from .playlists import YoutubeMusicPlaylistProvider, YoutubePlaylistAudioEnricher

__all__ = [
    "YoutubeMusicCatalogProvider",
    "YoutubeMusicLibraryProvider",
    "YoutubeMusicPlaylistProvider",
    "YoutubePlaylistAudioEnricher",
    "YoutubeSongCreditsProvider",
]
