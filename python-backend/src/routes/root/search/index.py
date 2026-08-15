"""Search the configured music catalog."""

from collections.abc import Mapping

from flask import jsonify, request

from src.lib.providers import CatalogSearchFilter, CatalogSearchQuery, ProviderError
from src.type_defs import RouteResponse

from .. import blueprint
from .._services import search_service


def parse_search_query(args: Mapping[str, str]) -> CatalogSearchQuery:
    """Interpret public query parameters and retain the songs default."""
    raw_filter = args.get("filter", CatalogSearchFilter.SONGS.value)
    try:
        search_filter = CatalogSearchFilter(raw_filter)
    except ValueError:
        search_filter = CatalogSearchFilter.SONGS
    return CatalogSearchQuery(text=args.get("q", ""), filter=search_filter)


@blueprint.route("/search")
def search() -> RouteResponse:
    try:
        return jsonify(search_service().search(parse_search_query(request.args)))
    except ProviderError as error:
        return jsonify({"error": str(error)}), 500
