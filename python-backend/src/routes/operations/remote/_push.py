"""Push desktop playback state to remote clients."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control
from ._services import _is_local


@blueprint.route("/remote/_push", methods=["POST"])
def remote_push() -> RouteResponse:
    if not _is_local():
        return jsonify({"error": "forbidden"}), 403
    remote_control().push_state(request.json or {})
    return jsonify({"ok": True})
