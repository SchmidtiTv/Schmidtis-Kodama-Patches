"""Audio streaming and progressive-proxy endpoints."""

from flask import Blueprint

blueprint = Blueprint("streaming", __name__)

from . import audio_stream, stream, stream_prepare, video_sync
