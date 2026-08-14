"""Poll queued remote-control commands."""

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control
from ._services import _is_local


@blueprint.route("/remote/_poll")
def remote_poll() -> RouteResponse:
    if not _is_local():
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"commands": remote_control().poll()})
