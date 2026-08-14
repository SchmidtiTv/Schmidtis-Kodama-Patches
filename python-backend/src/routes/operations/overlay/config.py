"""OBS overlay configuration."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import overlay_server


@blueprint.route("/overlay/config", methods=["GET", "POST"])
def overlay_config() -> RouteResponse:
    server = overlay_server()
    if request.method == "POST":
        # Accepts a flat v1 config (current frontend) OR a v2 doc → stored as v2.
        server.set_config(request.json or {})
        return jsonify({"ok": True})
    return jsonify(server.get_config())
