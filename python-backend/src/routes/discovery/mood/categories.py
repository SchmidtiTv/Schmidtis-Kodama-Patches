"""Mood and genre category route."""

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import music_session


@blueprint.route("/mood/categories")
def get_mood_categories() -> RouteResponse:
    """Return all mood/genre categories grouped by section (For you / Moods & moments / Genres)."""
    try:
        cats = music_session().get_active_client().get_mood_categories()
        groups: dict[str, list[dict[str, object]]] = {}
        seen_params: set[str] = set()
        for section_title, items in cats.items():
            chips = []
            for item in items:
                params = item.get("params", "")
                if params in seen_params:
                    continue
                seen_params.add(params)
                chips.append(
                    {
                        "title": item.get("title", ""),
                        "params": params,
                    }
                )
            if chips:
                groups[section_title] = chips
        return jsonify(groups)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
