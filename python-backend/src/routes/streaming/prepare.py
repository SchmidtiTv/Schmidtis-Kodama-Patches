"""Download audio to a temp file and return its local path."""

from flask import jsonify

from src.type_defs import RouteResponse

from . import blueprint
from ._services import stream_service


@blueprint.route("/stream-prepare/<video_id>")
def stream_prepare(video_id: str) -> RouteResponse:
    payload, status = stream_service().prepare_download(video_id)
    return jsonify(payload), status
