"""Search YouTube Music and normalize the supported result categories."""

from typing import Literal, cast

from flask import jsonify, request

from src.lib import YoutubeResponseMapper
from src.type_defs import RouteResponse

from . import blueprint
from ._formatters import song_result
from ._services import music_session


@blueprint.route("/search")
def search() -> RouteResponse:
    query = request.args.get("q", "")
    filter_type = request.args.get("filter", "songs")
    allowed_filters = {
        "all",
        "albums",
        "artists",
        "community_playlists",
        "episodes",
        "featured_playlists",
        "playlists",
        "podcasts",
        "profiles",
        "songs",
        "videos",
    }
    if filter_type not in allowed_filters:
        filter_type = "songs"
    if not query:
        return jsonify({"results": []})
    try:
        client_filter = (
            None
            if filter_type == "all"
            else cast(
                "Literal['albums', 'artists', 'community_playlists', 'episodes', 'featured_playlists', 'playlists', 'podcasts', 'profiles', 'songs', 'videos']",
                filter_type,
            )
        )
        results = music_session().get_active_client().search(query, filter=client_filter, limit=20)
        items = []
        for result in results:
            thumbnail = YoutubeResponseMapper.select_thumbnail(result.get("thumbnails", []))
            result_type = result.get("resultType") or filter_type.rstrip("s")
            if result_type == "song":
                items.append(song_result(result))
            elif result_type == "artist":
                # A "Top result" card carries the artist inside `artists` instead of
                # the `title`/`browseId` pair the regular artist rows use.
                top_artist = next(iter(result.get("artists") or []), {})
                browse_id = (
                    result.get("browseId", "")
                    or result.get("channelId", "")
                    or top_artist.get("id", "")
                )
                items.append(
                    {
                        "type": "artist",
                        "browseId": browse_id,
                        "title": result.get("title", "")
                        or result.get("artist", "")
                        or top_artist.get("name", ""),
                        "subtitle": result.get("subscribers", ""),
                        "thumbnail": thumbnail,
                    }
                )
            elif result_type == "album":
                artists = result.get("artists", [])
                items.append(
                    {
                        "type": "album",
                        "browseId": result.get("browseId", ""),
                        "title": result.get("title", ""),
                        "artists": ", ".join(artist["name"] for artist in artists)
                        or result.get("artist", ""),
                        "year": result.get("year", ""),
                        "thumbnail": thumbnail,
                    }
                )
            elif result_type == "playlist":
                browse_id = result.get("browseId", "")
                playlist_id = result.get("playlistId", "") or browse_id.removeprefix("VL")
                items.append(
                    {
                        "type": "playlist",
                        "playlistId": playlist_id,
                        "browseId": browse_id,
                        "title": result.get("title", ""),
                        "subtitle": result.get("author", ""),
                        "thumbnail": thumbnail,
                    }
                )
        return jsonify({"results": items})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


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
