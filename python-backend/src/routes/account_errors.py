"""HTTP translation for safe account application errors."""

from flask import Response, current_app, jsonify

from src.lib.accounts import AccountError


def account_error_response(error: Exception) -> tuple[Response, int]:
    if isinstance(error, AccountError):
        return jsonify({"error": error.safe_message}), error.status_code
    current_app.logger.exception("Unexpected account operation failure")
    return jsonify({"error": "Account operation failed."}), 500
