"""Complete Last.fm desktop authorization."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import lastfm_client, read_active_metadata, write_active_metadata


@blueprint.route("/session", methods=["POST"])
def lastfm_session() -> RouteResponse:
    token = (request.json or {}).get("token", "")
    if not token:
        return jsonify({"error": "missing_token"}), 400

    ok, response = lastfm_client().lastfm_call("auth.getSession", {"token": token}, signed=True)
    if not ok:
        return jsonify({"error": response.get("message", "session_failed")}), 400

    lastfm_session = response.get("session", {})
    if not isinstance(lastfm_session, dict):
        return jsonify({"error": "session_failed"}), 400
    key = lastfm_session.get("key", "")
    username = lastfm_session.get("name", "")
    if (
        not isinstance(key, str)
        or not key.strip()
        or not isinstance(username, str)
        or not username.strip()
    ):
        return jsonify({"error": "invalid_session"}), 502

    metadata = read_active_metadata()
    metadata["lastfm_session"] = key
    metadata["lastfm_user"] = username
    write_active_metadata(metadata)
    return jsonify({"connected": True, "username": username})
