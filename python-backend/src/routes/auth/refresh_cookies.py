"""Accept browser-refreshed anti-bot cookies."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session


@blueprint.route("/refresh-cookies", methods=["POST"])
def refresh_cookies() -> RouteResponse:
    cookie_string = ((request.json or {}).get("cookie") or "").strip()
    ok, error, has_psidts = music_session().apply_webview_cookies(cookie_string)
    if not ok:
        return jsonify({"error": error}), 400 if error in ("no_profile", "invalid") else 500
    return jsonify({"ok": True, "psidts": has_psidts})
