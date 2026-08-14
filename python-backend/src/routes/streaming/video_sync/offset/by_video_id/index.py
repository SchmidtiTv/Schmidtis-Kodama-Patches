"""Resolve the official-video counterpart and synchronization offset."""

from flask import jsonify

from src.type_defs import RouteResponse

from .... import blueprint
from ...._services import video_sync_service


@blueprint.route("/video-sync/offset/<video_id>")
def video_sync_offset(video_id: str) -> RouteResponse:
    return jsonify(video_sync_service().resolve_offset(video_id))
