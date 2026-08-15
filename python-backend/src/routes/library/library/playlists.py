"""Library playlist listing endpoint."""

from flask import jsonify

from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import library_service
from src.type_defs import RouteResponse


@blueprint.route("/library/playlists")
def library_playlists() -> RouteResponse:
    try:
        result: list[dict[str, str]] = []
        for playlist in library_service().playlists():
            item = {
                "playlistId": playlist.playlist_id,
                "title": playlist.title,
                "count": playlist.count,
                "thumbnail": playlist.thumbnail,
            }
            if playlist.description is not None:
                item["description"] = playlist.description
            result.append(item)
        return jsonify({"playlists": result})
    except Exception as error:
        return account_error_response(error)
