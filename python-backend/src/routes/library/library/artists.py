"""Library artist listing endpoint."""

from flask import jsonify

from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import library_service
from src.type_defs import RouteResponse


@blueprint.route("/library/artists")
def library_artists() -> RouteResponse:
    try:
        artists = library_service().artists()
        return jsonify(
            {
                "artists": [
                    {
                        "browseId": artist.browse_id,
                        "artist": artist.artist,
                        "songs": artist.songs,
                        "thumbnail": artist.thumbnail,
                    }
                    for artist in artists
                ]
            }
        )
    except Exception as error:
        return account_error_response(error)
