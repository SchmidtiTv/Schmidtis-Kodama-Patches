"""Shared access to the lyrics service."""

from typing import cast

from flask import current_app

from src.lib.integrations.unison import UnisonClient
from src.lib.music.lyrics import LyricsService


def lyrics_service() -> LyricsService:
    return cast("LyricsService", current_app.extensions["lyrics_service"])


def unison_client() -> UnisonClient:
    return cast("UnisonClient", current_app.extensions["unison_client"])
