"""Library listings for playlists, albums, and artists."""

from flask import jsonify

from src.lib import YoutubeResponseMapper
from src.routes.library import blueprint
from src.routes.library._services import music_session, profiles
from src.type_defs import RouteResponse


@blueprint.route("/library/playlists")
def library_playlists() -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                rows = db.execute(
                    "SELECT playlist_id, title, description, (SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id=p.playlist_id) FROM playlists p ORDER BY updated_at DESC"
                ).fetchall()
            result = [
                {
                    "playlistId": r[0],
                    "title": r[1],
                    "description": r[2],
                    "count": str(r[3]),
                    "thumbnail": "",
                }
                for r in rows
            ]
            return jsonify({"playlists": result})
        # ``None`` follows every continuation. Numeric limits stop at a page boundary and
        # silently truncate larger libraries (for example, limit=50 returned roughly 75 of 229).
        playlists = session.get_active_client().get_library_playlists(limit=None)
        result = []
        for p in playlists:
            # Liked Songs has one canonical entry in the app sidebar. The same
            # account-relative "LM" playlist can also appear in YouTube Music's
            # library response, which otherwise creates a duplicate playlist card.
            if p.get("playlistId") == "LM":
                continue
            result.append(
                {
                    "playlistId": p.get("playlistId", ""),
                    "title": p.get("title", ""),
                    "count": p.get("count", ""),
                    "thumbnail": YoutubeResponseMapper.select_thumbnail(p.get("thumbnails", [])),
                }
            )
        return jsonify({"playlists": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
