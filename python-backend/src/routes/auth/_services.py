"""Shared access to profile authentication services."""

from typing import cast

from flask import current_app

from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.profiles.profile import Profile


def profiles() -> Profile:
    return cast("Profile", current_app.extensions["profile_repository"])


def music_session() -> YoutubeMusicSession:
    return cast("YoutubeMusicSession", current_app.extensions["youtube_music_session"])
