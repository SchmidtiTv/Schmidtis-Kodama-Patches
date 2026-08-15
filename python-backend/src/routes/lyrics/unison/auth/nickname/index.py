"""Forward validated signed Unison nickname changes."""

from flask import request

from src.lib.integrations.unison import NicknameUpdate
from src.routes.lyrics._services import unison_client
from src.type_defs import RouteResponse

from .... import blueprint
from ..._forwarding import signed_envelope, unison_error_response, unison_response


@blueprint.route("/unison/auth/nickname", methods=["PUT", "DELETE"])
def unison_nickname() -> RouteResponse:
    try:
        result = unison_client().update_nickname(
            NicknameUpdate(signed_envelope(), delete=request.method == "DELETE")
        )
        return unison_response(result)
    except Exception as error:
        return unison_error_response(error)
