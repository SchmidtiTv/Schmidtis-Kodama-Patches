"""Fetch a playlist Mix analysis job."""

from flask import jsonify

from src.routes.library import blueprint
from src.routes.library._services import mix_analysis_service, music_session
from src.type_defs import RouteResponse

from ..._validation import _valid_playlist_id


@blueprint.route("/playlist/<playlist_id>/mix/analysis/<job_id>")
def get_playlist_mix_analysis(playlist_id: str, job_id: str) -> RouteResponse:
    if not _valid_playlist_id(playlist_id):
        return jsonify({"error": "playlistId is required"}), 400
    job = mix_analysis_service().get_job(music_session().state.current_profile, playlist_id, job_id)
    if job is None:
        return jsonify({"error": "analysis job not found"}), 404
    return jsonify(job)
