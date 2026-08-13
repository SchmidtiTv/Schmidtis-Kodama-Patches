"""Validate the active authentication session."""

import os

from flask import jsonify

from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session, profiles


@blueprint.route("/validate")
def validate_auth() -> RouteResponse:
    session = music_session()
    if session.state.adding_account:
        return jsonify({"valid": False, "reason": "adding_account"})
    if session.state.ytm is None:
        return jsonify({"valid": False, "reason": "no_profile"})

    name = session.state.current_profile
    if not name:
        return jsonify({"valid": False, "reason": "no_profile"})

    profile_repository = profiles()
    if profile_repository.is_local(name):
        if os.path.exists(profile_repository.metadata_file_path(name)):
            return jsonify({"valid": True, "profile": name, "type": "local"})
        return jsonify({"valid": False, "reason": "no_profile"})
    if os.path.exists(profile_repository.profile_file_path(name)):
        return jsonify({"valid": True, "profile": name, "type": "google"})
    return jsonify({"valid": False, "reason": "no_profile"})
