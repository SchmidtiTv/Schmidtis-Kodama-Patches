"""Remove tracks from a playlist."""

import time

from flask import jsonify, request

from src.routes.library import blueprint
from src.routes.library._services import music_session, playlist_cache, profiles
from src.type_defs import RouteResponse


@blueprint.route("/playlist/<playlist_id>/remove", methods=["POST"])
def playlist_remove_tracks(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        data = request.get_json() or {}
        videos = data.get("videos", [])
        if not videos:
            return jsonify({"error": "videos required"}), 400
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                for v in videos:
                    svid = v.get("setVideoId")
                    if svid:
                        db.execute(
                            "DELETE FROM playlist_tracks WHERE playlist_id=? AND set_video_id=?",
                            (playlist_id, svid),
                        )
                    else:
                        db.execute(
                            "DELETE FROM playlist_tracks WHERE playlist_id=? AND video_id=?",
                            (playlist_id, v.get("videoId", "")),
                        )
                db.execute(
                    "UPDATE playlists SET updated_at=? WHERE playlist_id=?",
                    (int(time.time()), playlist_id),
                )
                db.commit()
            return jsonify({"ok": True})
        session.get_active_client().remove_playlist_items(playlist_id, videos)
        playlist_cache().purge_playlist_cache(playlist_id, profile_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
