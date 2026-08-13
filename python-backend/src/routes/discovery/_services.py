"""Shared services for discovery routes."""

from typing import cast

from flask import current_app

from src.lib.music.youtube_music import YoutubeMusicSession


def music_session() -> YoutubeMusicSession:
    return cast("YoutubeMusicSession", current_app.extensions["youtube_music_session"])
