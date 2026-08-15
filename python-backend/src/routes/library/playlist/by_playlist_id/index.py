"""Fetch or delete a playlist."""

from flask import jsonify

from src.lib.accounts import required_id
from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import playlist_service
from src.type_defs import RouteResponse


@blueprint.route("/playlist/<playlist_id>", methods=["DELETE"])
def delete_playlist(playlist_id: str) -> RouteResponse:
    try:
        playlist_service().delete(required_id(playlist_id, "playlistId"))
        return jsonify({"ok": True})
    except Exception as error:
        return account_error_response(error)


@blueprint.route("/playlist/<playlist_id>")
def get_playlist(playlist_id: str) -> RouteResponse:
    try:
        return jsonify(playlist_service().get(required_id(playlist_id, "playlistId")))
    except Exception as error:
        return account_error_response(error)
