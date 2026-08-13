"""Return local backend health status."""

from flask import jsonify

from src.type_defs import RouteResponse

from . import blueprint


@blueprint.route("/status")
def status() -> RouteResponse:
    return jsonify({"ok": True, "message": "Kodama Backend laeuft"})
