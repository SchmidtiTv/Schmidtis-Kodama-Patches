"""Local Mix configuration for a playlist.

Mix settings are intentionally stored by Kodama per profile. They do not alter or
attempt to synchronize with the corresponding YouTube Music playlist.
"""

from flask import jsonify, request

from src.lib.music.playlist_mix import PlaylistMixConfigurationError
from src.routes.library import blueprint
from src.routes.library._services import music_session, playlist_mix
from src.type_defs import RouteResponse

from ._validation import _valid_playlist_id


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
