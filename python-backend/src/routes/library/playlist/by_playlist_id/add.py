"""Add tracks to a playlist."""

from flask import jsonify, request

from src.lib.accounts import parse_add_playlist_items
from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import playlist_service
from src.type_defs import RouteResponse


@blueprint.route("/playlist/<playlist_id>/add", methods=["POST"])
def playlist_add_tracks(playlist_id: str) -> RouteResponse:
    try:
        data = request.get_json(silent=True)
        command = parse_add_playlist_items(playlist_id, data if data is not None else {})
        playlist_service().add_items(command)
        return jsonify({"ok": True})
    except Exception as error:
        return account_error_response(error)
