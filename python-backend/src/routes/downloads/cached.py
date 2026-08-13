"""Serve, list, and delete songs from the permanent download cache."""

from flask import jsonify, request, send_file

from src.type_defs import RouteResponse

from . import blueprint
from ._services import download_service


@blueprint.route("/song/cached/<video_id>")
def serve_cached_song(video_id: str) -> RouteResponse:
    service = download_service()
    path = service.song_audio_path(video_id)
    if not path:
        return jsonify({"error": "not cached"}), 404
    return send_file(path, mimetype=service.audio_mime_type(path))


@blueprint.route("/song/cached/list")
def list_cached_songs() -> RouteResponse:
    return jsonify({"songs": download_service().list_cached()})


@blueprint.route("/song/cached/<video_id>", methods=["DELETE"])
def delete_cached_song(video_id: str) -> RouteResponse:
    download_service().delete_cached(video_id)
    return jsonify({"ok": True})


@blueprint.route("/songs/cached/delete-batch", methods=["POST"])
def delete_cached_songs_batch() -> RouteResponse:
    data = request.get_json() or {}
    video_ids = data.get("videoIds", [])
    service = download_service()
    for video_id in video_ids:
        service.delete_cached(video_id)
    return jsonify({"ok": True, "removed": len(video_ids)})
