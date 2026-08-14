"""Start a background song download by video ID."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .... import blueprint
from ...._services import download_service


@blueprint.route("/song/download/<video_id>", methods=["POST"])
def download_song(video_id: str) -> RouteResponse:
    service = download_service()
    if service.song_audio_path(video_id):
        service.status[video_id] = "done"
        return jsonify({"ok": True, "status": "done"})
    if service.status.get(video_id) == "downloading":
        return jsonify({"ok": True, "status": "downloading"})
    data = request.get_json() or {}
    meta = {
        "videoId": video_id,
        "title": data.get("title", ""),
        "artists": data.get("artists", ""),
        "album": data.get("album", ""),
        "duration": data.get("duration", ""),
        "thumbnail": data.get("thumbnail", ""),
    }
    if service.start(video_id, meta) is False:
        return jsonify({"error": "download queue is full"}), 429
    return jsonify({"ok": True, "status": "downloading"})
