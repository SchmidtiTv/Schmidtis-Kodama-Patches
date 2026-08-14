"""List liked songs for the active local or YouTube Music profile."""

from flask import jsonify, request

from src.lib.music.audio_versions import prefer_audio_versions
from src.type_defs import RouteResponse

from .. import blueprint
from .._formatters import is_signed_out_ytmusic_error, song_result
from .._services import metadata_cache, music_session, profiles

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


@blueprint.route("/liked")
def liked_songs() -> RouteResponse:
    session = music_session()
    profile_repository = profiles()
    profile_name = session.state.current_profile
    try:
        if profile_repository.is_local(profile_name):
            with profile_repository.local_database(profile_name or "default") as database:
                rows = database.execute(
                    "SELECT video_id, title, artists, album, thumbnail, duration "
                    "FROM liked_songs ORDER BY liked_at DESC"
                ).fetchall()
            tracks = [
                {
                    "videoId": row[0],
                    "title": row[1],
                    "artists": row[2],
                    "album": row[3],
                    "thumbnail": row[4],
                    "duration": row[5],
                }
                for row in rows
            ]
            return jsonify({"tracks": tracks})

        offset = request.args.get("offset", default=0, type=int)
        limit = request.args.get("limit", default=DEFAULT_PAGE_SIZE, type=int)
        if offset is None or offset < 0 or limit is None or not 1 <= limit <= MAX_PAGE_SIZE:
            return (
                jsonify(
                    {"error": "offset must be non-negative and limit must be between 1 and 100"}
                ),
                400,
            )

        # The upstream client continues a playlist only up to its limit. Request
        # just enough tracks for this page, then return the requested slice.
        # This keeps opening Liked Songs to one small API request.
        songs = session.get_active_client().get_liked_songs(limit=offset + limit)
        raw_tracks = [track for track in songs.get("tracks", []) if track.get("videoId")]
        page_tracks = raw_tracks[offset : offset + limit]
        page_tracks = prefer_audio_versions(
            session.get_system_client(), None, page_tracks, metadata_cache()
        )
        total = songs.get("trackCount", len(raw_tracks))
        try:
            total = int(total)
        except (TypeError, ValueError):
            total = len(raw_tracks)
        return jsonify(
            {
                "tracks": [song_result(track) for track in page_tracks],
                "total": total,
                "offset": offset,
                "hasMore": offset + len(page_tracks) < total,
            }
        )
    except Exception as error:
        if is_signed_out_ytmusic_error(error):
            return jsonify({"error": "YouTube session expired", "code": "auth_expired"}), 401
        return jsonify({"error": str(error)}), 500
