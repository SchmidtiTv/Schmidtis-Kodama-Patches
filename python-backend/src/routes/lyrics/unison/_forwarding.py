"""Helpers for forwarding signed Unison requests."""

import requests
from flask import jsonify, request

from src.type_defs import RouteResponse


def forward_signed_request(method: str, path: str) -> RouteResponse:
    """Forward the frontend's signed JSON envelope without interpreting it."""
    try:
        response = requests.request(
            method,
            f"https://unison.boidu.dev{path}",
            json=request.get_json(silent=True),
            timeout=12,
        )
        content_type = response.headers.get("Content-Type", "application/json")
        return response.content, response.status_code, {"Content-Type": content_type}
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 502
