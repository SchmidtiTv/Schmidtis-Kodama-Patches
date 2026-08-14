"""Add tracks to a playlist."""

import time
import uuid

from flask import jsonify, request

from src.routes.library import blueprint
from src.routes.library._services import music_session, playlist_cache, profiles
from src.type_defs import RouteResponse


@blueprint.route("/playlist/<playlist_id>/add", methods=["POST"])
def playlist_add_tracks(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        data = request.get_json() or {}
        video_ids = data.get("videoIds", [])
        if not video_ids:
            return jsonify({"error": "videoIds required"}), 400
        if profile_repo.is_local(profile_name):
            tracks_meta = {t["videoId"]: t for t in data.get("tracks", []) if "videoId" in t}
            now = int(time.time())
            with profile_repo.local_database(profile_name or "default") as db:
                max_pos = db.execute(
                    "SELECT COALESCE(MAX(position),0) FROM playlist_tracks WHERE playlist_id=?",
                    (playlist_id,),
                ).fetchone()[0]
                for i, vid in enumerate(video_ids):
                    meta = tracks_meta.get(vid, {})
                    svid = str(uuid.uuid4())
                    db.execute(
                        "INSERT INTO playlist_tracks (playlist_id, video_id, title, artists, album, thumbnail, duration, set_video_id, position, added_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            playlist_id,
                            vid,
                            meta.get("title", ""),
                            meta.get("artists", ""),
                            meta.get("album", ""),
                            meta.get("thumbnail", ""),
                            meta.get("duration", ""),
                            svid,
                            max_pos + i + 1,
                            now,
                        ),
                    )
                db.execute(
                    "UPDATE playlists SET updated_at=? WHERE playlist_id=?", (now, playlist_id)
                )
                db.commit()
            return jsonify({"ok": True})
        session.get_active_client().add_playlist_items(playlist_id, video_ids)
        playlist_cache().purge_playlist_cache(playlist_id, profile_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
