"""Report song download status by video ID."""

from flask import jsonify

from src.type_defs import RouteResponse

from ..... import blueprint
from ....._services import download_service


@blueprint.route("/song/download/status/<video_id>")
def download_status(video_id: str) -> RouteResponse:
    service = download_service()
    if service.song_audio_path(video_id):
        return jsonify({"status": "done"})
    return jsonify({"status": service.status.get(video_id, "not_found")})
