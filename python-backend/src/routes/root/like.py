"""Update the liked state of a song for the active profile."""

import time

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session, profiles


@blueprint.route("/like/<video_id>", methods=["POST"])
def like_song(video_id: str) -> RouteResponse:
    data = request.get_json(silent=True) or {}
    rating = data.get("rating", "LIKE")
    session = music_session()
    profile_repository = profiles()
    profile_name = session.state.current_profile
    try:
        if profile_repository.is_local(profile_name):
            with profile_repository.local_database(profile_name or "default") as database:
                if rating == "LIKE":
                    database.execute(
                        "INSERT OR REPLACE INTO liked_songs "
                        "(video_id, title, artists, album, thumbnail, duration, liked_at) VALUES (?,?,?,?,?,?,?)",
                        (
                            video_id,
                            data.get("title", ""),
                            data.get("artists", ""),
                            data.get("album", ""),
                            data.get("thumbnail", ""),
                            data.get("duration", ""),
                            int(time.time()),
                        ),
                    )
                else:
                    database.execute("DELETE FROM liked_songs WHERE video_id=?", (video_id,))
                database.commit()
            return jsonify({"ok": True, "rating": rating})

        session.get_active_client().rate_song(video_id, rating)
        return jsonify({"ok": True, "rating": rating})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
