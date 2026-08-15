"""Return the active profile's liked-song video identifiers."""

from flask import jsonify

from src.routes.account_errors import account_error_response
from src.type_defs import RouteResponse

from .. import blueprint
from .._services import liked_songs_service


@blueprint.route("/liked/ids")
def liked_ids() -> RouteResponse:
    try:
        return jsonify({"ids": sorted(liked_songs_service().ids())})
    except Exception as error:
        return account_error_response(error)
