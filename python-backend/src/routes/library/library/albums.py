"""Library album listing endpoint."""

from flask import jsonify

from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import library_service
from src.type_defs import RouteResponse


@blueprint.route("/library/albums")
def library_albums() -> RouteResponse:
    try:
        albums = library_service().albums()
        return jsonify(
            {
                "albums": [
                    {
                        "browseId": album.browse_id,
                        "title": album.title,
                        "artists": album.artists,
                        "year": album.year,
                        "thumbnail": album.thumbnail,
                    }
                    for album in albums
                ]
            }
        )
    except Exception as error:
        return account_error_response(error)
