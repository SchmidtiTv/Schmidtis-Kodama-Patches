"""Return playback state to an approved remote client."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control


@blueprint.route("/remote/state")
def remote_state() -> RouteResponse:
    payload, status = remote_control().get_state(
        request.args.get("token"), request.args.get("deviceId")
    )
    return jsonify(payload), status
