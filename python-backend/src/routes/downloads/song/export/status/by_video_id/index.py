"""Report song export status by video ID."""

from flask import jsonify

from src.type_defs import RouteResponse

from ..... import blueprint
from ....._services import export_service


@blueprint.route("/song/export/status/<video_id>")
def export_status(video_id: str) -> RouteResponse:
    return jsonify({"status": export_service().status.get(video_id, "not_found")})
