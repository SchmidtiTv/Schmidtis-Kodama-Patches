"""Band-member lookup endpoint for an artist."""

from flask import jsonify, request

from src.lib import BandMemberLookupError
from src.routes.library import blueprint
from src.routes.library._services import band_member_finder
from src.type_defs import RouteResponse


@blueprint.route("/artist/<browse_id>/members")
def artist_members(browse_id: str) -> RouteResponse:
    artist_name = request.args.get("name", "").strip()
    if not artist_name:
        return jsonify({"error": "artist name is required"}), 400
    try:
        return jsonify({"members": band_member_finder().find(artist_name)})
    except BandMemberLookupError:
        return jsonify({"error": "band members unavailable"}), 502
