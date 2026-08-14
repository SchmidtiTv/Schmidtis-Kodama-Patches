"""Album and artist reference endpoint for a song."""

from flask import jsonify

from src.routes.library import blueprint
from src.routes.library._services import music_session
from src.type_defs import RouteResponse


@blueprint.route("/song/info/<video_id>")
def song_info(video_id: str) -> RouteResponse:
    """Return albumBrowseId and artistBrowseId for a given video ID."""
    try:
        client = music_session().get_active_client()
        data = client.get_song(video_id)
        details = data.get("videoDetails", {})
        artist_id = ""
        try:
            result = client.search(
                f"{details.get('title', '')} {details.get('author', '')}",
                filter="songs",
                limit=1,
            )
            if result:
                hit = result[0]
                artists = hit.get("artists", [])
                artist_id = (artists[0].get("id") or "") if artists else ""
                album = hit.get("album") or {}
                album_id = album.get("id") or ""
            else:
                album_id = ""
        except Exception:
            album_id = ""
        return jsonify({"artistBrowseId": artist_id, "albumBrowseId": album_id})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
