"""Read or delete locally imported lyrics for a video."""

from flask import jsonify

from src.type_defs import RouteResponse

from .... import blueprint
from ...._services import lyrics_service


@blueprint.route("/lyrics/custom/<video_id>", methods=["GET"])
def get_custom_lyrics(video_id: str) -> RouteResponse:
    lyrics = lyrics_service().get_custom(video_id)
    if lyrics is None:
        # This is a routine capability check before falling back to online lyric
        # providers. Return an explicit empty result so WebKit does not log an
        # expected 404 for every track without imported lyrics.
        return jsonify({"found": False})
    return jsonify(lyrics)


@blueprint.route("/lyrics/custom/<video_id>", methods=["DELETE"])
def delete_custom_lyrics(video_id: str) -> RouteResponse:
    if lyrics_service().delete_custom(video_id):
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404
