"""Mark account creation as in progress."""

from flask import jsonify

from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session


@blueprint.route("/begin-add", methods=["POST"])
def begin_add() -> RouteResponse:
    music_session().state.adding_account = True
    return jsonify({"ok": True})
