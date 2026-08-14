"""Serve or delete a cached song by video ID."""

from flask import jsonify, send_file

from src.type_defs import RouteResponse

from .... import blueprint
from ...._services import download_service


@blueprint.route("/song/cached/<video_id>")
def serve_cached_song(video_id: str) -> RouteResponse:
    service = download_service()
    path = service.song_audio_path(video_id)
    if not path:
        return jsonify({"error": "not cached"}), 404
    return send_file(path, mimetype=service.audio_mime_type(path))


@blueprint.route("/song/cached/<video_id>", methods=["DELETE"])
def delete_cached_song(video_id: str) -> RouteResponse:
    download_service().delete_cached(video_id)
    return jsonify({"ok": True})
