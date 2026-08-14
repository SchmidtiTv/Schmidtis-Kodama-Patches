"""Register a phone with LAN remote control."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control


@blueprint.route("/remote/hello", methods=["POST"])
def remote_hello() -> RouteResponse:
    payload, status = remote_control().hello(request.json or {})
    return jsonify(payload), status
