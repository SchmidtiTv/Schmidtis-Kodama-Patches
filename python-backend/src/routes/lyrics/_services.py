"""Shared access to the lyrics service."""

from typing import cast

from flask import current_app

from src.lib.music.lyrics import LyricsService


def lyrics_service() -> LyricsService:
    return cast("LyricsService", current_app.extensions["lyrics_service"])
