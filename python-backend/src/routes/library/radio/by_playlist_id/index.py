"""Radio (watch-playlist) endpoint."""

from flask import jsonify, request

from src.lib.accounts import AccountValidationError, required_id
from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import playlist_service
from src.type_defs import RouteResponse


@blueprint.route("/radio/<playlist_id>")
def get_radio(playlist_id: str) -> RouteResponse:
    try:
        normalized_playlist_id = required_id(playlist_id, "playlistId")
        video_id = request.args.get("videoId", "").strip()
        if normalized_playlist_id == "_" and not video_id:
            raise AccountValidationError("videoId required")
        return jsonify(playlist_service().radio(normalized_playlist_id, video_id))
    except Exception as error:
        return account_error_response(error)
