"""Validated feedback submission route."""

from flask import Blueprint, current_app, jsonify, request

from src.lib.feedback import FeedbackNotConfiguredError, FeedbackValidationError
from src.lib.providers import ProviderError
from src.type_defs import RouteResponse

from ._services import feedback_service

blueprint = Blueprint("feedback", __name__)


@blueprint.route("/feedback", methods=["POST"])
def submit_feedback() -> RouteResponse:
    try:
        data = request.get_json(silent=True)
        feedback_service().submit(data if data is not None else {})
        return jsonify({"ok": True})
    except FeedbackNotConfiguredError:
        return jsonify({"error": "feedback_not_configured"}), 503
    except FeedbackValidationError as error:
        return jsonify({"error": str(error)}), 400
    except ProviderError:
        return jsonify({"error": "feedback_unavailable"}), 502
    except Exception:
        current_app.logger.exception("Unexpected feedback submission failure")
        return jsonify({"error": "feedback_unavailable"}), 500
