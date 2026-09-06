"""Return local backend health status."""

from flask import jsonify

from src.lib.runtime.versions import backend_versions
from src.type_defs import RouteResponse

from . import blueprint


@blueprint.route("/status")
def status() -> RouteResponse:
    """Return backend health and diagnostic dependency versions."""
    return jsonify({"ok": True, "message": "Kodama Backend laeuft", "versions": backend_versions()})
