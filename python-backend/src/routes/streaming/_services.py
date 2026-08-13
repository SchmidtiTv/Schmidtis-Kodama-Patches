"""Shared access to the audio stream service."""

from typing import cast

from flask import current_app

from src.lib.music.stream import StreamService
from src.lib.music.video_sync import VideoSyncService


def stream_service() -> StreamService:
    return cast("StreamService", current_app.extensions["stream_service"])


def video_sync_service() -> VideoSyncService:
    return cast("VideoSyncService", current_app.extensions["video_sync_service"])
