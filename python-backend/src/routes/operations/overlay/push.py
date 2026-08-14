"""OBS overlay state updates."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import overlay_server


@blueprint.route("/overlay/push", methods=["POST"])
def overlay_push() -> RouteResponse:
    overlay_server().update_state(request.json or {})
    return jsonify({"ok": True})
