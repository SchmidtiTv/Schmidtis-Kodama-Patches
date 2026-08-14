"""OBS overlay server status."""

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import overlay_server


@blueprint.route("/overlay/status")
def overlay_status() -> RouteResponse:
    return jsonify(overlay_server().status())
