"""Prewarm a video's audio stream URL."""

from flask import jsonify

from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import stream_service


@blueprint.route("/audio-stream/<video_id>/warm")
def audio_stream_warm(video_id: str) -> RouteResponse:
    return jsonify({"ok": stream_service().warm(video_id)})
