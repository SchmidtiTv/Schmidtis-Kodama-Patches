"""List songs in the permanent download cache."""

from flask import jsonify

from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import download_service


@blueprint.route("/song/cached/list")
def list_cached_songs() -> RouteResponse:
    return jsonify({"songs": download_service().list_cached()})
