"""Edit a playlist."""

from flask import jsonify, request

from src.lib.accounts import parse_edit_playlist
from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import playlist_service
from src.type_defs import RouteResponse


@blueprint.route("/playlist/<playlist_id>/edit", methods=["POST"])
def playlist_edit(playlist_id: str) -> RouteResponse:
    try:
        data = request.get_json(silent=True)
        command = parse_edit_playlist(playlist_id, data if data is not None else {})
        playlist_service().edit(command)
        return jsonify({"ok": True})
    except Exception as error:
        return account_error_response(error)
