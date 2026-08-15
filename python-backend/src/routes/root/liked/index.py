"""List liked songs for the active local or YouTube Music profile."""

from flask import jsonify, request

from src.lib.accounts import liked_song_json, local_liked_song_json
from src.lib.providers import LikedSongsQuery
from src.routes.account_errors import account_error_response
from src.type_defs import RouteResponse

from .. import blueprint
from .._services import liked_songs_service

DEFAULT_PAGE_SIZE = 50


@blueprint.route("/liked")
def liked_songs() -> RouteResponse:
    try:
        offset = request.args.get("offset", default=0, type=int)
        limit = request.args.get("limit", default=DEFAULT_PAGE_SIZE, type=int)
        if offset is None or limit is None:
            raise ValueError
        query = LikedSongsQuery(offset=offset, limit=limit)
        page = liked_songs_service().songs(query)
        if page.total is None:
            return jsonify({"tracks": [local_liked_song_json(track) for track in page.tracks]})
        return jsonify(
            {
                "tracks": [liked_song_json(track) for track in page.tracks],
                "total": page.total,
                "offset": page.offset,
                "hasMore": page.has_more,
            }
        )
    except ValueError:
        return (
            jsonify({"error": "offset must be non-negative and limit must be between 1 and 100"}),
            400,
        )
    except Exception as error:
        return account_error_response(error)
