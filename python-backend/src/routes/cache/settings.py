"""Read and update runtime cache feature flags."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import cache_settings


@blueprint.route("/cache/settings", methods=["GET", "POST"])
def cache_settings_route() -> RouteResponse:
    settings = cache_settings()
    if request.method == "POST":
        settings.update(request.get_json(silent=True) or {})
        return jsonify({"ok": True})
    snapshot = getattr(settings, "snapshot", None)
    return jsonify(snapshot() if callable(snapshot) else settings.enabled)
