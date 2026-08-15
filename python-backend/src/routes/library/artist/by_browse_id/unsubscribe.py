"""Artist unsubscription endpoint."""

from collections.abc import Mapping

from flask import jsonify, request

from src.lib.accounts import AccountValidationError, required_id
from src.routes.account_errors import account_error_response
from src.routes.library import blueprint
from src.routes.library._services import artist_subscription_service
from src.type_defs import RouteResponse


@blueprint.route("/artist/<browse_id>/unsubscribe", methods=["POST"])
def artist_unsubscribe(browse_id: str) -> RouteResponse:
    try:
        data = request.get_json(silent=True)
        if data is None:
            data = {}
        if not isinstance(data, Mapping):
            raise AccountValidationError("JSON object required")
        channel_id = required_id(data.get("channelId") or browse_id, "browseId")
        artist_subscription_service().unsubscribe(channel_id)
        return jsonify({"ok": True})
    except Exception as error:
        return account_error_response(error)
