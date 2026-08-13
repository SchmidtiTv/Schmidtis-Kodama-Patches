"""Local Mix configuration for playlists.

Mix settings are intentionally stored by Kodama per profile. They do not alter or
attempt to synchronize with the corresponding YouTube Music playlist.
"""

from flask import jsonify, request

from src.lib.music.playlist_mix import PlaylistMixConfigurationError
from src.type_defs import RouteResponse

from . import blueprint
from ._services import mix_analysis_service, music_session, playlist_mix


def _valid_playlist_id(playlist_id: str) -> bool:
    return bool(playlist_id.strip()) and len(playlist_id) <= 256


@blueprint.route("/playlist/<playlist_id>/mix")
def get_playlist_mix(playlist_id: str) -> RouteResponse:
    if not _valid_playlist_id(playlist_id):
        return jsonify({"error": "playlistId is required"}), 400
    return jsonify(playlist_mix().get(music_session().state.current_profile, playlist_id))


@blueprint.route("/playlist/<playlist_id>/mix", methods=["PUT"])
def update_playlist_mix(playlist_id: str) -> RouteResponse:
    if not _valid_playlist_id(playlist_id):
        return jsonify({"error": "playlistId is required"}), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Mix configuration is required"}), 400
    try:
        return jsonify(
            playlist_mix().update(music_session().state.current_profile, playlist_id, data)
        )
    except PlaylistMixConfigurationError as error:
        return jsonify({"error": str(error)}), 400


@blueprint.route("/playlist/<playlist_id>/mix", methods=["DELETE"])
def delete_playlist_mix(playlist_id: str) -> RouteResponse:
    if not _valid_playlist_id(playlist_id):
        return jsonify({"error": "playlistId is required"}), 400
    playlist_mix().delete(music_session().state.current_profile, playlist_id)
    return jsonify({"ok": True})


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


@blueprint.route("/playlist/<playlist_id>/mix/analysis/<job_id>")
def get_playlist_mix_analysis(playlist_id: str, job_id: str) -> RouteResponse:
    if not _valid_playlist_id(playlist_id):
        return jsonify({"error": "playlistId is required"}), 400
    job = mix_analysis_service().get_job(music_session().state.current_profile, playlist_id, job_id)
    if job is None:
        return jsonify({"error": "analysis job not found"}), 404
    return jsonify(job)
