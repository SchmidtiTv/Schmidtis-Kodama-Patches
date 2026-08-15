"""Playlist creation endpoint."""

from flask import jsonify, request

from src.lib.accounts import parse_create_playlist
from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import playlist_service
from src.type_defs import RouteResponse


@blueprint.route("/playlist/create", methods=["POST"])
def create_playlist() -> RouteResponse:
    try:
        data = request.get_json(silent=True)
        command = parse_create_playlist(data if data is not None else {})
        created = playlist_service().create(command)
        return jsonify({"ok": True, "playlistId": created.playlist_id})
    except Exception as error:
        return account_error_response(error)
