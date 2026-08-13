"""Shared app state used by the cache endpoints."""

from typing import cast

from flask import current_app

from src.lib.music.download import DownloadService
from src.lib.music.playlist import Playlist
from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.runtime.cache import CacheSettings
from src.lib.runtime.metadata_cache import MetadataCache


def cache_settings() -> CacheSettings:
    return cast("CacheSettings", current_app.extensions["cache_settings"])


def metadata_cache() -> MetadataCache | None:
    """Return the structured cache store when available (older test apps omit it)."""
    return cast("MetadataCache | None", current_app.extensions.get("metadata_cache"))


def music_session() -> YoutubeMusicSession:
    return cast("YoutubeMusicSession", current_app.extensions["youtube_music_session"])


def playlist_cache() -> Playlist:
    return cast("Playlist", current_app.extensions["playlist_cache"])


def download_service() -> DownloadService:
    return cast("DownloadService", current_app.extensions["download_service"])
