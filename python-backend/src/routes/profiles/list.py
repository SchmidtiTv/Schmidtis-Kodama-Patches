"""List available profiles."""

from flask import jsonify

from . import blueprint
from ._services import music_session, profiles
from src.type_defs import RouteResponse


@blueprint.route("", methods=["GET"])
@blueprint.route("/", methods=["GET"])
def list_profiles() -> RouteResponse:
    session = music_session()
    # Only an explicit False counts: last_authenticated is None until the first cookie
    # refresh runs, and warning on that would fire on every launch.
    session_expired = session.state.last_authenticated is False
    return jsonify(
        {
            "profiles": profiles().list_profiles(session.state.current_profile, session_expired),
            "current": session.state.current_profile,
        }
    )
