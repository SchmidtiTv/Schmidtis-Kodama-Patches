"""Return sidebar search suggestions."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import music_session


@blueprint.route("/search/suggestions")
def search_suggestions() -> RouteResponse:
    """Return a compact, de-duplicated set of titles for sidebar autocomplete."""
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"suggestions": []})
    try:
        results = music_session().get_active_client().search(query, filter=None, limit=6)
        suggestions: list[str] = []
        seen: set[str] = set()
        for result in results:
            title = result.get("title") if isinstance(result, dict) else None
            if not isinstance(title, str) or not title.strip() or title.casefold() in seen:
                continue
            seen.add(title.casefold())
            suggestions.append(title)
        return jsonify({"suggestions": suggestions})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
