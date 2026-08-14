"""Translate lyric lines through Google Translate."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from . import blueprint
from ._services import lyrics_service


@blueprint.route("/translate-lyrics", methods=["POST"])
def translate_lyrics() -> RouteResponse:
    data = request.get_json() or {}
    lines = data.get("lines", [])
    target_lang = data.get("target_lang", "DE").upper()
    if not lines:
        return jsonify({"translations": []})
    try:
        return jsonify({"translations": lyrics_service().translate(lines, target_lang)})
    except Exception as error:
        return jsonify({"error": str(error), "translations": list(lines)}), 500
