"""Mood/genre categories and the playlists within a category."""

from typing import cast

from flask import jsonify, request

from src.lib import YoutubeResponseMapper
from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session


# Old server.py: _parse_two_row_item
def _parse_two_row_item(renderer: dict[str, object]) -> dict[str, object] | None:
    """Parse a musicTwoRowItemRenderer (used on mood/genre category pages) into
    our generic item shape. Handles playlists, albums, artists and songs.
    """
    title = ""
    try:
        title_data = cast("dict[str, object]", renderer["title"])
        runs = cast("list[dict[str, object]]", title_data["runs"])
        title = str(runs[0]["text"])
    except (KeyError, IndexError, TypeError):
        pass
    subtitle = ""
    try:
        subtitle_data = cast("dict[str, object]", renderer.get("subtitle", {}))
        subtitle = "".join(
            str(run.get("text", ""))
            for run in cast("list[dict[str, object]]", subtitle_data.get("runs", []))
        )
    except (KeyError, TypeError):
        pass
    thumb = None
    try:
        thumbnail_renderer = cast("dict[str, object]", renderer["thumbnailRenderer"])
        music_thumbnail = cast("dict[str, object]", thumbnail_renderer["musicThumbnailRenderer"])
        thumbnail = cast("dict[str, object]", music_thumbnail["thumbnail"])
        thumbs = cast("list[dict[str, object]]", thumbnail["thumbnails"])
        thumb = YoutubeResponseMapper.select_thumbnail(thumbs)
    except (KeyError, TypeError):
        pass
    nav = cast("dict[str, object]", renderer.get("navigationEndpoint", {}) or {})
    if "watchPlaylistEndpoint" in nav:
        endpoint = cast("dict[str, object]", nav["watchPlaylistEndpoint"])
        return {
            "type": "playlist",
            "playlistId": endpoint.get("playlistId", ""),
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if "watchEndpoint" in nav:
        we = cast("dict[str, object]", nav["watchEndpoint"])
        return {
            "type": "song",
            "videoId": we.get("videoId", ""),
            "playlistId": we.get("playlistId", ""),
            "title": title,
            "artists": subtitle,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    browse_id = str(
        cast("dict[str, object]", nav.get("browseEndpoint", {}) or {}).get("browseId", "")
    )
    if browse_id.startswith("VL"):
        return {
            "type": "playlist",
            "playlistId": browse_id[2:],
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if browse_id.startswith("MPRE"):
        return {
            "type": "album",
            "browseId": browse_id,
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if browse_id.startswith("UC"):
        return {
            "type": "artist",
            "browseId": browse_id,
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if browse_id:
        return {
            "type": "playlist",
            "playlistId": browse_id,
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    return None


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
