"""Approve or reject a LAN remote-control device."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control
from ._services import _is_local


@blueprint.route("/remote/_device", methods=["POST"])
def remote_device() -> RouteResponse:
    if not _is_local():
        return jsonify({"error": "forbidden"}), 403
    payload, status = remote_control().device_action(request.json or {})
    return jsonify(payload), status
