"""Artist subscription endpoint."""

from flask import jsonify, request

from src.routes.library import blueprint
from src.routes.library._services import music_session
from src.type_defs import RouteResponse


@blueprint.route("/artist/<browse_id>/subscribe", methods=["POST"])
def artist_subscribe(browse_id: str) -> RouteResponse:
    try:
        data = request.get_json(silent=True) or {}
        channel_id = data.get("channelId") or browse_id
        music_session().get_active_client().subscribe_artists([channel_id])
        return jsonify({"ok": True})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
