"""Start Mix analysis for a playlist."""

from flask import jsonify, request

from src.routes.library import blueprint
from src.routes.library._services import mix_analysis_service, music_session
from src.type_defs import RouteResponse

from .._validation import _valid_playlist_id


@blueprint.route("/playlist/<playlist_id>/mix/analysis", methods=["POST"])
def start_playlist_mix_analysis(playlist_id: str) -> RouteResponse:
    if not _valid_playlist_id(playlist_id):
        return jsonify({"error": "playlistId is required"}), 400
    data = request.get_json(silent=True)
    tracks = data.get("tracks") if isinstance(data, dict) else None
    if not isinstance(tracks, list) or not tracks or len(tracks) > 10_000:
        return jsonify({"error": "tracks must be a non-empty array"}), 400
    normalized: list[dict[str, str]] = []
    for track in tracks:
        if not isinstance(track, dict):
            return jsonify({"error": "tracks entries must be objects"}), 400
        instance_id, video_id = track.get("instanceId"), track.get("videoId")
        if not all(
            isinstance(value, str) and value.strip() and len(value) <= 256
            for value in (instance_id, video_id)
        ):
            return jsonify({"error": "tracks require instanceId and videoId"}), 400
        normalized.append(
            {"instanceId": str(instance_id).strip(), "videoId": str(video_id).strip()}
        )
    return (
        jsonify(
            mix_analysis_service().start(
                music_session().state.current_profile, playlist_id, normalized
            )
        ),
        202,
    )
