"""Queue a command from an approved remote client."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control


@blueprint.route("/remote/cmd", methods=["POST"])
def remote_cmd() -> RouteResponse:
    payload, status = remote_control().command(request.json or {})
    return jsonify(payload), status
