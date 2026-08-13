"""Shared application services for standalone routes."""

from typing import cast

from flask import current_app

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
