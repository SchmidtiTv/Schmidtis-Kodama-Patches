"""Mood and genre playlist route."""

from typing import cast

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import music_session
from ._formatters import _parse_two_row_item


@blueprint.route("/mood/playlists")
def get_mood_playlists() -> RouteResponse:
    try:
        params = request.args.get("params", "")
        if not params:
            return jsonify({"error": "params required"}), 400
        # Direct browse + robust manual parse — ytmusicapi.get_mood_playlists raises
        # KeyError('musicTwoRowItemRenderer') on genre category pages.
        response = cast(
            "dict[str, object]",
            music_session()
            .get_active_client()
            ._send_request(
                "browse", {"browseId": "FEmusic_moods_and_genres_category", "params": params}
            ),
        )
        try:
            contents = cast("dict[str, object]", response["contents"])
            browse = cast("dict[str, object]", contents["singleColumnBrowseResultsRenderer"])
            tab = cast("list[dict[str, object]]", browse["tabs"])[0]
            tab_renderer = cast("dict[str, object]", tab["tabRenderer"])
            content = cast("dict[str, object]", tab_renderer["content"])
            section_renderer = cast("dict[str, object]", content["sectionListRenderer"])
            section_list = cast("list[dict[str, object]]", section_renderer["contents"])
        except (KeyError, IndexError, TypeError):
            section_list: list[dict[str, object]] = []
        result: list[dict[str, object]] = []
        seen: set[object] = set()
        for section in section_list:
            items: list[dict[str, object]] = []
            if "gridRenderer" in section:
                grid = cast("dict[str, object]", section["gridRenderer"])
                items = cast("list[dict[str, object]]", grid.get("items", []))
            elif "musicCarouselShelfRenderer" in section:
                shelf = cast("dict[str, object]", section["musicCarouselShelfRenderer"])
                items = cast("list[dict[str, object]]", shelf.get("contents", []))
            for it in items:
                renderer = cast("dict[str, object] | None", it.get("musicTwoRowItemRenderer"))
                if not renderer:
                    continue
                parsed = _parse_two_row_item(renderer)
                if not parsed:
                    continue
                key = (
                    parsed.get("playlistId")
                    or parsed.get("browseId")
                    or parsed.get("videoId")
                    or parsed.get("title")
                )
                if key in seen:
                    continue
                seen.add(key)
                result.append(parsed)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
