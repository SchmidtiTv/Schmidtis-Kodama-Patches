"""Create a profile from copied browser request headers."""

import threading
from typing import cast

from flask import jsonify, request

from src.lib import ProfileAuthHeaders
from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session, profiles


@blueprint.route("/setup", methods=["POST"])
def setup_auth() -> RouteResponse:
    data = request.json or {}
    raw_headers = data.get("headers_raw", "").strip()
    profile_name = data.get("profile_name", "")
    display_name = data.get("display_name", profile_name)
    if not raw_headers or not profile_name:
        return jsonify({"error": "headers_raw und profile_name erforderlich"}), 400

    if raw_headers.startswith("curl "):
        headers = cast("dict[str, str]", ProfileAuthHeaders.parse_curl_command(raw_headers))
    else:
        headers = cast("dict[str, str]", ProfileAuthHeaders.parse_raw_headers(raw_headers))
    if "cookie" not in headers:
        return (
            jsonify(
                {
                    "error": "The following entries are missing in your headers: cookie, x-goog-authuser. "
                    "Please try a different request (such as /browse) and make sure you are logged in."
                }
            ),
            400,
        )

    headers.setdefault("x-goog-authuser", "0")
    headers.setdefault("origin", "https://music.youtube.com")
    headers.setdefault("x-origin", "https://music.youtube.com")

    profile_repository = profiles()
    session = music_session()
    profile_repository.write_auth_headers(profile_name, session.prepare_auth_headers(headers))
    profile_repository.write_metadata(profile_name, {"displayName": display_name})
    try:
        session.activate_verified_profile(profile_name)
        threading.Thread(
            target=session.refresh_account_info, args=(profile_name,), daemon=True
        ).start()
        return jsonify({"ok": True, "profile": profile_name})
    except Exception as error:
        profile_repository.remove_auth_headers(profile_name)
        return jsonify({"error": str(error)}), 500
