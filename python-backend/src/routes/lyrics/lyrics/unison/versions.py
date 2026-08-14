"""List the community lyric versions available through Unison."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import lyrics_service


@blueprint.route("/lyrics/unison/versions")
def unison_versions() -> RouteResponse:
    return jsonify(
        {
            "versions": lyrics_service().unison_versions(
                video_id=request.args.get("videoId", ""),
                title=request.args.get("title", "") or request.args.get("song", ""),
                artist=request.args.get("artist", ""),
                album=request.args.get("album", ""),
                duration=request.args.get("duration", ""),
            )
        }
    )
