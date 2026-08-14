"""Report the active song download queue."""

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import download_service


@blueprint.route("/downloads/queue")
def downloads_queue() -> RouteResponse:
    return jsonify({"queue": download_service().queue_snapshot()})
