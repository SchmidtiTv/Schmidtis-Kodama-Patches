"""Read and update Composer Bridge audio caching."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import composer_bridge


@blueprint.route("/composer-bridge/autocache", methods=["GET", "POST"])
def composer_bridge_autocache() -> RouteResponse:
    bridge = composer_bridge()
    body = request.get_json(silent=True) or {}
    if request.method == "POST" and "enabled" in body:
        bridge.set_autocache_enabled(body["enabled"])
    return jsonify({"enabled": bridge.autocache_enabled})
