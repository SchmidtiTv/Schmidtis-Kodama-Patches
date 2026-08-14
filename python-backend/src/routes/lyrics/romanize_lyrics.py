"""Romanize Japanese lyric lines."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import lyrics_service


@blueprint.route("/romanize-lyrics", methods=["POST"])
def romanize_lyrics() -> RouteResponse:
    lines = (request.get_json() or {}).get("lines", [])
    if not lines:
        return jsonify({"romanizations": []})
    try:
        return jsonify({"romanizations": lyrics_service().romanize(lines)})
    except ImportError:
        return (
            jsonify({"error": "pykakasi nicht installiert.", "romanizations": [""] * len(lines)}),
            503,
        )
