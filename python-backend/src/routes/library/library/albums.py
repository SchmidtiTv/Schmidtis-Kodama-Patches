"""Library album listing endpoint."""

from typing import Any, cast

from flask import jsonify

from src.lib import YoutubeResponseMapper
from src.routes.library import blueprint
from src.routes.library._services import music_session, profiles
from src.type_defs import RouteResponse


@blueprint.route("/library/albums")
def library_albums() -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        if profile_repo.is_local(profile_name):
            return jsonify({"albums": []})
        client = cast(Any, session.get_active_client())
        albums = client.get_library_albums(limit=None)
        result = []
        for album in albums:
            artists = ", ".join(artist["name"] for artist in album.get("artists", []))
            result.append(
                {
                    "browseId": album.get("browseId", ""),
                    "title": album.get("title", ""),
                    "artists": artists,
                    "year": album.get("year", ""),
                    "thumbnail": YoutubeResponseMapper.select_thumbnail(
                        album.get("thumbnails", [])
                    ),
                }
            )
        return jsonify({"albums": result})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
