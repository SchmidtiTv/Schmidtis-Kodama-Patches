"""Start the OBS overlay server."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import overlay_server


@blueprint.route("/overlay/server/start", methods=["POST"])
def overlay_server_start() -> RouteResponse:
    port = (request.json or {}).get("port", 9848)
    ok = overlay_server().start(int(port))
    return jsonify({"ok": ok, "port": port})
