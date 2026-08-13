"""Shared services for the download, export, and tool-update routes."""

from typing import cast

from flask import current_app

from src.lib.integrations.ffmpeg import FFmpeg
from src.lib.integrations.ytdlp import YTDLP
from src.lib.music.download import DownloadService
from src.lib.music.export import ExportService
from src.lib.music.youtube_music import YoutubeMusicSession


def download_service() -> DownloadService:
    return cast("DownloadService", current_app.extensions["download_service"])


def export_service() -> ExportService:
    return cast("ExportService", current_app.extensions["export_service"])


def ffmpeg() -> FFmpeg:
    return cast("FFmpeg", current_app.extensions["ffmpeg"])


def ytdlp() -> YTDLP:
    return cast("YTDLP", current_app.extensions["ytdlp"])


def music_session() -> YoutubeMusicSession:
    return cast("YoutubeMusicSession", current_app.extensions["youtube_music_session"])
