"""YouTube Music account-history integration."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session, profiles


@blueprint.route("/ytmusic/history", methods=["POST"])
def add_history_item() -> RouteResponse:
    """Register an opted-in play in the active account's YT Music history."""
    data = request.get_json(silent=True) or {}
    video_id = data.get("videoId")
    if not isinstance(video_id, str) or not video_id.strip():
        return jsonify({"error": "videoId required"}), 400

    session = music_session()
    profile_name = session.state.current_profile
    if not profile_name or profiles().is_local(profile_name):
        return jsonify({"error": "authenticated profile required"}), 403

    try:
        client = session.get_active_client()
        song = client.get_song(video_id.strip())
        playback_url = ((song or {}).get("playbackTracking") or {}).get("videostatsPlaybackUrl")
        if not playback_url:
            return jsonify({"error": "no_playback_tracking"}), 502
        response = client.add_history_item(song)
        status = getattr(response, "status_code", None)
        return jsonify({"ok": status == 204, "status": status})
    except Exception as error:
        return jsonify({"error": str(error)}), 502
