"""Look up lyrics from the configured providers."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import lyrics_service


@blueprint.route("/lyrics")
def get_lyrics() -> RouteResponse:
    return jsonify(
        lyrics_service().get_lyrics(
            title=request.args.get("title", ""),
            artist=request.args.get("artist", ""),
            album=request.args.get("album", ""),
            duration=request.args.get("duration", ""),
            source=request.args.get("source", "auto"),
            video_id=request.args.get("videoId", ""),
        )
    )
