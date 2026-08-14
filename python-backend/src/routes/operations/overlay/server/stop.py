"""Stop the OBS overlay server."""

from flask import jsonify

from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import overlay_server


@blueprint.route("/overlay/server/stop", methods=["POST"])
def overlay_server_stop() -> RouteResponse:
    overlay_server().stop()
    return jsonify({"ok": True})
