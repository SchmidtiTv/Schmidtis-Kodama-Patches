"""Playlist creation endpoint."""

import time
import uuid

from flask import jsonify, request

from src.routes.library import blueprint
from src.routes.library._services import music_session, profiles
from src.type_defs import RouteResponse


@blueprint.route("/playlist/create", methods=["POST"])
def create_playlist() -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        if not title:
            return jsonify({"error": "Title is required"}), 400
        description = data.get("description", "")
        privacy = data.get("privacyStatus", "PRIVATE")
        if profile_repo.is_local(profile_name):
            playlist_id = str(uuid.uuid4())
            now = int(time.time())
            with profile_repo.local_database(profile_name or "default") as db:
                db.execute(
                    "INSERT INTO playlists (playlist_id, title, description, privacy, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (playlist_id, title, description, privacy, now, now),
                )
                db.commit()
            return jsonify({"ok": True, "playlistId": playlist_id})
        video_ids = data.get("videoIds")
        result = session.get_active_client().create_playlist(
            title, description, privacy_status=privacy, video_ids=video_ids
        )
        return jsonify({"ok": True, "playlistId": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
