"""OBS overlay: preview page + SSE on the main app, plus control endpoints.

The page and stream are mirrored on the main backend (always running) so the
editor preview iframe works even when the dedicated OBS server is disabled.
"""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import overlay_server


@blueprint.route("/overlay")
def overlay_page() -> RouteResponse:
    return overlay_server().page_response()


@blueprint.route("/overlay/stream")
def overlay_stream() -> RouteResponse:
    return overlay_server().stream_response()


@blueprint.route("/overlay/push", methods=["POST"])
def overlay_push() -> RouteResponse:
    overlay_server().update_state(request.json or {})
    return jsonify({"ok": True})


@blueprint.route("/overlay/config", methods=["GET", "POST"])
def overlay_config() -> RouteResponse:
    server = overlay_server()
    if request.method == "POST":
        # Accepts a flat v1 config (current frontend) OR a v2 doc → stored as v2.
        server.set_config(request.json or {})
        return jsonify({"ok": True})
    return jsonify(server.get_config())


@blueprint.route("/overlay/server/start", methods=["POST"])
def overlay_server_start() -> RouteResponse:
    port = (request.json or {}).get("port", 9848)
    ok = overlay_server().start(int(port))
    return jsonify({"ok": ok, "port": port})


@blueprint.route("/overlay/server/stop", methods=["POST"])
def overlay_server_stop() -> RouteResponse:
    overlay_server().stop()
    return jsonify({"ok": True})


@blueprint.route("/overlay/status")
def overlay_status() -> RouteResponse:
    return jsonify(overlay_server().status())
