"""yt-dlp version check and in-place updater."""

from flask import jsonify

from src.type_defs import RouteResponse

from . import blueprint
from ._services import ytdlp


@blueprint.route("/ytdlp/check-update")
def ytdlp_check_update() -> RouteResponse:
    return jsonify(ytdlp().check_update())


@blueprint.route("/ytdlp/update", methods=["POST"])
def ytdlp_update() -> RouteResponse:
    payload, status = ytdlp().update()
    return jsonify(payload), status
