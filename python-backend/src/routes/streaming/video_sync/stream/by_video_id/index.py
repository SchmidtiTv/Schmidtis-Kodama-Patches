"""Resolve a playable official-video URL."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .... import blueprint
from ...._services import video_sync_service


@blueprint.route("/video-sync/stream/<video_id>")
def video_sync_stream(video_id: str) -> RouteResponse:
    max_height = request.args.get("maxHeight", type=int)
    payload, status = video_sync_service().resolve_video_stream(video_id, max_height)
    return jsonify(payload), status
