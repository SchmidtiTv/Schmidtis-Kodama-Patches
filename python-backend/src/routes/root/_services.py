"""Shared application services for standalone routes."""

from typing import cast

from flask import current_app

from src.lib.accounts import LikedSongsService, SongRatingService
from src.lib.images import ImageProxyService
from src.lib.music.search import SearchService
from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.profiles.profile import Profile
from src.lib.runtime.cache import CacheSettings
from src.lib.runtime.metadata_cache import MetadataCache


def cache_settings() -> CacheSettings:
    return cast("CacheSettings", current_app.extensions["cache_settings"])


def metadata_cache() -> MetadataCache:
    return cast("MetadataCache", current_app.extensions["metadata_cache"])


def music_session() -> YoutubeMusicSession:
    return cast("YoutubeMusicSession", current_app.extensions["youtube_music_session"])


def profiles() -> Profile:
    return cast("Profile", current_app.extensions["profile_repository"])


def search_service() -> SearchService:
    return cast("SearchService", current_app.extensions["search_service"])


def liked_songs_service() -> LikedSongsService:
    return cast("LikedSongsService", current_app.extensions["liked_songs_service"])


def song_rating_service() -> SongRatingService:
    return cast("SongRatingService", current_app.extensions["song_rating_service"])


def image_proxy_service() -> ImageProxyService:
    return cast("ImageProxyService", current_app.extensions["image_proxy_service"])
