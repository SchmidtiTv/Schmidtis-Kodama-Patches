"""HTTP-adapter helpers for typed Unison operations."""

from collections.abc import Mapping

from flask import Response, current_app, jsonify, request

from src.lib.integrations.unison import NicknameCheckResult, UnisonResult
from src.lib.providers import ProviderAuthenticationError, ProviderError


def signed_envelope() -> Mapping[str, object]:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("Signed Unison envelope must be an object")
    return payload


def unison_response(result: UnisonResult | NicknameCheckResult) -> tuple[Response, int]:
    return jsonify(result.payload), result.status_code


def unison_error_response(error: Exception) -> tuple[Response, int]:
    if isinstance(error, ValueError):
        return jsonify({"success": False, "error": "invalid_request"}), 400
    if isinstance(error, ProviderAuthenticationError):
        return jsonify({"success": False, "error": "authentication_required"}), 401
    if isinstance(error, ProviderError):
        return jsonify({"success": False, "error": "unison_unavailable"}), 502
    current_app.logger.exception("Unexpected Unison forwarding failure")
    return jsonify({"success": False, "error": "unison_unavailable"}), 500
