"""Return sidebar search suggestions."""

from flask import jsonify, request

from src.lib.providers import ProviderError
from src.type_defs import RouteResponse

from .. import blueprint
from .._services import search_service


@blueprint.route("/search/suggestions")
def search_suggestions() -> RouteResponse:
    try:
        return jsonify(search_service().suggestions(request.args.get("q", "")))
    except ProviderError as error:
        return jsonify({"error": str(error)}), 500
