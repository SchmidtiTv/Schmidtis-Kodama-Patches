"""Return the active profile's liked-song video identifiers."""

from flask import jsonify

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import music_session, profiles


@blueprint.route("/liked/ids")
def liked_ids() -> RouteResponse:
    session = music_session()
    profile_repository = profiles()
    profile_name = session.state.current_profile
    try:
        if profile_repository.is_local(profile_name):
            with profile_repository.local_database(profile_name or "default") as database:
                ids = [
                    row[0]
                    for row in database.execute("SELECT video_id FROM liked_songs").fetchall()
                ]
            return jsonify({"ids": ids})

        songs = session.get_active_client().get_liked_songs()
        ids = [track.get("videoId") for track in songs.get("tracks", []) if track.get("videoId")]
        return jsonify({"ids": ids})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
