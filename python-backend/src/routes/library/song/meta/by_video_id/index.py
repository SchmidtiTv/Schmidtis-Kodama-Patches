"""Minimal song metadata endpoint."""

from flask import jsonify

from src.routes.library import blueprint
from src.routes.library._services import music_session
from src.type_defs import RouteResponse


@blueprint.route("/song/meta/<video_id>")
def song_meta(video_id: str) -> RouteResponse:
    """Turn a shared song deep link into a playable track object."""
    try:
        info = music_session().get_active_client().get_song(video_id) or {}
        video_details = info.get("videoDetails", {}) or {}
        thumbnails = (video_details.get("thumbnail") or {}).get("thumbnails") or []
        thumbnail = thumbnails[-1]["url"] if thumbnails else None
        seconds = int(video_details.get("lengthSeconds") or 0)
        duration = f"{seconds // 60}:{seconds % 60:02d}" if seconds else None
        return jsonify(
            {
                "videoId": video_details.get("videoId") or video_id,
                "title": video_details.get("title"),
                "artists": video_details.get("author"),
                "thumbnail": thumbnail,
                "duration": duration,
            }
        )
    except Exception as error:
        return jsonify({"error": str(error)}), 502
