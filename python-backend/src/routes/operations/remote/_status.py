"""Report LAN remote-control status."""

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control
from ._services import _is_local


@blueprint.route("/remote/_status")
def remote_status() -> RouteResponse:
    if not _is_local():
        return jsonify({"error": "forbidden"}), 403
    return jsonify(remote_control().status_payload())
