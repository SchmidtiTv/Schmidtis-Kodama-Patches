"""Audio streaming and progressive-proxy endpoints."""

from flask import Blueprint

blueprint = Blueprint("streaming", __name__)

from . import audio, prepare, stream, video_sync
