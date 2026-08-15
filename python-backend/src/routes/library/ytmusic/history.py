"""YouTube Music account-history integration."""

from collections.abc import Mapping

from flask import jsonify, request

from src.lib.accounts import AccountValidationError, required_id
from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import listening_history_service
from src.type_defs import RouteResponse


@blueprint.route("/ytmusic/history", methods=["POST"])
def add_history_item() -> RouteResponse:
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            raise AccountValidationError("JSON object required")
        video_id = required_id(data.get("videoId"), "videoId")
        status = listening_history_service().add(video_id)
        return jsonify({"ok": True, "status": status})
    except Exception as error:
        return account_error_response(error)
