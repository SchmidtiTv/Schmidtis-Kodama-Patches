"""Delete a batch of cached songs."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import download_service


@blueprint.route("/songs/cached/delete-batch", methods=["POST"])
def delete_cached_songs_batch() -> RouteResponse:
    data = request.get_json() or {}
    video_ids = data.get("videoIds", [])
    service = download_service()
    for video_id in video_ids:
        service.delete_cached(video_id)
    return jsonify({"ok": True, "removed": len(video_ids)})
