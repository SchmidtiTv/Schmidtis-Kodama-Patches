"""Library artist listing endpoint."""

from typing import Any, cast

from flask import jsonify

from src.lib import YoutubeResponseMapper
from src.routes.library import blueprint
from src.routes.library._services import music_session, profiles
from src.type_defs import RouteResponse


@blueprint.route("/library/artists")
def library_artists() -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        if profile_repo.is_local(profile_name):
            return jsonify({"artists": []})
        client = cast(Any, session.get_active_client())
        artists = client.get_library_artists(limit=None)
        result = []
        for artist in artists:
            result.append(
                {
                    "browseId": artist.get("browseId", ""),
                    "artist": artist.get("artist", ""),
                    "songs": artist.get("songs", ""),
                    "thumbnail": YoutubeResponseMapper.select_thumbnail(
                        artist.get("thumbnails", [])
                    ),
                }
            )
        return jsonify({"artists": result})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
