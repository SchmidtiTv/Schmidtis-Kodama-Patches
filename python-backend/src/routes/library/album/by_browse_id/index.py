"""Album detail endpoint."""

from flask import jsonify, request

from src.lib.providers import ProviderError
from src.routes.library import blueprint
from src.routes.library._services import album_details_service
from src.type_defs import RouteResponse


@blueprint.route("/album/<browse_id>")
def get_album(browse_id: str) -> RouteResponse:
    try:
        force_refresh = request.args.get("refresh") == "1"
        return jsonify(album_details_service().get(browse_id, force_refresh=force_refresh))
    except ProviderError as error:
        return jsonify({"error": str(error)}), 500
