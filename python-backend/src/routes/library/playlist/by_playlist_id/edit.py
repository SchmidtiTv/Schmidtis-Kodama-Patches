"""Edit a playlist."""

import time

from flask import jsonify, request

from src.routes.library import blueprint
from src.routes.library._services import music_session, playlist_cache, profiles
from src.type_defs import RouteResponse


@blueprint.route("/playlist/<playlist_id>/edit", methods=["POST"])
def playlist_edit(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        data = request.get_json() or {}
        title = data.get("title")
        description = data.get("description")
        privacy = data.get("privacyStatus")
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                if title:
                    db.execute(
                        "UPDATE playlists SET title=?, updated_at=? WHERE playlist_id=?",
                        (title, int(time.time()), playlist_id),
                    )
                if description is not None:
                    db.execute(
                        "UPDATE playlists SET description=? WHERE playlist_id=?",
                        (description, playlist_id),
                    )
                if privacy:
                    db.execute(
                        "UPDATE playlists SET privacy=? WHERE playlist_id=?", (privacy, playlist_id)
                    )
                db.commit()
            return jsonify({"ok": True})
        session.get_active_client().edit_playlist(
            playlist_id, title=title, description=description, privacyStatus=privacy
        )
        playlist_cache().purge_playlist_cache(playlist_id, profile_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
