"""Store locally imported lyrics for a video."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import lyrics_service


@blueprint.route("/lyrics/custom", methods=["POST"])
def save_custom_lyrics() -> RouteResponse:
    data = request.get_json() or {}
    video_id = data.get("videoId", "").strip()
    content = data.get("content", "")
    lyric_format = data.get("format", "lrc").lower()
    if not video_id or not content or lyric_format not in ("lrc", "ttml"):
        return jsonify({"error": "invalid request"}), 400
    lyrics_service().save_custom(video_id, content, lyric_format)
    return jsonify({"ok": True})
