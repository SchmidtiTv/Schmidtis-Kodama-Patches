"""Normalized song credits endpoint."""

from flask import current_app, jsonify

from src.lib.providers import ProviderError
from src.routes.library import blueprint
from src.routes.library._services import song_credits_service
from src.type_defs import RouteResponse


@blueprint.route("/song/credits/<video_id>")
def get_song_credits(video_id: str) -> RouteResponse:
    try:
        credits = song_credits_service().get_credits(video_id)
        return jsonify({"description": credits.description})
    except ValueError:
        return jsonify({"error": "invalid_video_id"}), 400
    except ProviderError:
        return jsonify({"error": "credits_unavailable"}), 502
    except Exception:
        current_app.logger.exception("Unexpected song credits failure")
        return jsonify({"error": "credits_unavailable"}), 500
