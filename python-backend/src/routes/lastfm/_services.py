"""Shared access to Last.fm and active-profile services."""

from collections.abc import Mapping
from typing import cast

from flask import current_app

from src.lib.integrations.lastfm import LastFM
from src.lib.music.youtube_music import YoutubeMusicSession
from src.lib.profiles.profile import Profile


def lastfm_client() -> LastFM:
    return cast("LastFM", current_app.extensions["lastfm_client"])


def profile_repository() -> Profile:
    return cast("Profile", current_app.extensions["profile_repository"])


def active_profile_name() -> str:
    session = cast("YoutubeMusicSession", current_app.extensions["youtube_music_session"])
    return session.state.current_profile or "default"


def read_active_metadata() -> dict[str, object]:
    return profile_repository().read_metadata(active_profile_name())


def write_active_metadata(metadata: Mapping[str, object]) -> None:
    profile_repository().write_metadata(active_profile_name(), metadata)
