"""Resolve a public Unison display name."""

from flask import jsonify

from src.type_defs import RouteResponse

from .... import blueprint
from ...._services import lyrics_service


@blueprint.route("/unison/displayname/<key_id>")
def unison_displayname(key_id: str) -> RouteResponse:
    return jsonify({"displayName": lyrics_service().display_name(key_id)})
