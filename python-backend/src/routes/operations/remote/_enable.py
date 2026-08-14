"""Enable or configure LAN remote control."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control
from ._services import _is_local


@blueprint.route("/remote/_enable", methods=["POST"])
def remote_enable() -> RouteResponse:
    if not _is_local():
        return jsonify({"error": "forbidden"}), 403
    return jsonify(remote_control().enable(request.json or {}))
