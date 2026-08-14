"""Check whether the managed FFmpeg binary has an update."""

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import ffmpeg


@blueprint.route("/ffmpeg/check-update")
def ffmpeg_check_update() -> RouteResponse:
    """Compare installed ffmpeg with the current platform download source."""
    return jsonify(ffmpeg().check_update())
