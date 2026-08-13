"""Log out the active Google profile without removing its metadata."""

from flask import jsonify

from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session, profiles


@blueprint.route("/logout", methods=["POST"])
def logout() -> RouteResponse:
    session = music_session()
    name = session.state.current_profile
    if not name:
        return jsonify({"error": "Kein aktives Profil"}), 400

    profile_repository = profiles()
    if profile_repository.is_local(name):
        return jsonify({"error": "Lokales Profil kann nicht abgemeldet werden"}), 400

    profile_repository.remove_auth_headers(name)
    profile_repository.update_metadata(name, logged_out=True)
    session.clear_active_profile()
    return jsonify({"ok": True})
