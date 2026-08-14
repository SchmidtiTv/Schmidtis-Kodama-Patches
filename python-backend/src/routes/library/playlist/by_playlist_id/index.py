"""Fetch or delete a playlist."""

from flask import jsonify

from src.lib.music.audio_versions import prefer_audio_versions
from src.routes.library import blueprint
from src.routes.library._services import (
    metadata_cache,
    music_session,
    playlist_cache,
    profiles,
)
from src.type_defs import RouteResponse

from .._formatters import format_track


@blueprint.route("/playlist/<playlist_id>", methods=["DELETE"])
def delete_playlist(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                db.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
                db.execute("DELETE FROM playlists WHERE playlist_id=?", (playlist_id,))
                db.commit()
            return jsonify({"ok": True})
        session.get_active_client().delete_playlist(playlist_id)
        playlist_cache().purge_playlist_cache(playlist_id, profile_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/playlist/<playlist_id>")
def get_playlist(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    resolver = session.get_system_client()
    try:
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                if playlist_id == "LM":
                    rows = db.execute(
                        "SELECT video_id, title, artists, album, thumbnail, duration FROM liked_songs ORDER BY liked_at DESC"
                    ).fetchall()
                    tracks = [
                        {
                            "videoId": r[0],
                            "setVideoId": r[0],
                            "title": r[1],
                            "artists": r[2],
                            "album": r[3],
                            "thumbnail": r[4],
                            "duration": r[5],
                        }
                        for r in rows
                    ]
                    return jsonify({"title": "Gelikte Songs", "thumbnail": "", "tracks": tracks})
                pl_row = db.execute(
                    "SELECT title FROM playlists WHERE playlist_id=?", (playlist_id,)
                ).fetchone()
                rows = None
                if pl_row:
                    rows = db.execute(
                        "SELECT video_id, set_video_id, title, artists, album, thumbnail, duration FROM playlist_tracks WHERE playlist_id=? ORDER BY position ASC",
                        (playlist_id,),
                    ).fetchall()
            if pl_row and rows is not None:
                tracks = [
                    {
                        "videoId": r[0],
                        "setVideoId": r[1],
                        "title": r[2],
                        "artists": r[3],
                        "album": r[4],
                        "thumbnail": r[5],
                        "duration": r[6],
                    }
                    for r in rows
                ]
                return jsonify({"title": pl_row[0], "thumbnail": "", "tracks": tracks})
            # Not a local playlist -> fall through to the online fetch below.

        # "LM" is the special Liked Songs playlist
        if playlist_id == "LM":
            songs = session.get_active_client().get_liked_songs()
            raw_tracks = [track for track in songs.get("tracks", []) if track.get("videoId")]
            tracks = [
                format_track(track)
                for track in prefer_audio_versions(resolver, None, raw_tracks, metadata_cache())
            ]
            return jsonify({"title": "Liked Songs", "thumbnail": "", "tracks": tracks})

        playlist = session.get_active_client().get_playlist(playlist_id, limit=None)
        raw_tracks = [t for t in playlist.get("tracks", []) if t.get("videoId")]
        raw_tracks = prefer_audio_versions(resolver, playlist_id, raw_tracks, metadata_cache())
        tracks = [format_track(t) for t in raw_tracks]
        return jsonify(
            {
                "title": playlist.get("title", ""),
                "thumbnail": (playlist.get("thumbnails") or [{}])[-1].get("url", ""),
                "tracks": tracks,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
