"""Report whether FFmpeg is available for song exports."""

from flask import jsonify

from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import ffmpeg


@blueprint.route("/song/export/ffmpeg-available")
def ffmpeg_available() -> RouteResponse:
    return jsonify({"available": ffmpeg().available()})
