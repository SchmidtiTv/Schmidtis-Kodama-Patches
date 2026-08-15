"""Public song statistics endpoint."""

import re

from flask import current_app, jsonify

from src.lib.providers.errors import ProviderError
from src.routes.library import blueprint
from src.routes.library._services import song_statistics_service
from src.type_defs import RouteResponse

VIDEO_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")


@blueprint.route("/song/stats/<video_id>")
def song_stats(video_id: str) -> RouteResponse:
    if VIDEO_ID_PATTERN.fullmatch(video_id) is None:
        return jsonify({"error": "invalid video id"}), 400

    try:
        return jsonify(song_statistics_service().get_statistics(video_id))
    except ProviderError:
        return jsonify({"error": "stats unavailable"}), 502
    except Exception:
        current_app.logger.exception("Unexpected song statistics failure")
        return jsonify({"error": "internal server error"}), 500
