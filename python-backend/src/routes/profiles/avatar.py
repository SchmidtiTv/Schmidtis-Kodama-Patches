"""Update a profile avatar."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import profiles


@blueprint.route("/avatar", methods=["POST"])
def set_profile_avatar() -> RouteResponse:
    data = request.json or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "Fehlende Parameter"}), 400

    profiles().update_metadata(name, avatar=data.get("avatar", ""))
    return jsonify({"ok": True})
