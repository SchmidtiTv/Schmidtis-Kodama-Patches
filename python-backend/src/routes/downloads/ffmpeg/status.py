"""Report FFmpeg availability."""

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import ffmpeg


@blueprint.route("/ffmpeg/status")
def ffmpeg_status() -> RouteResponse:
    """Returns whether ffmpeg is available next to the server binary."""
    return jsonify({"available": ffmpeg().available()})
