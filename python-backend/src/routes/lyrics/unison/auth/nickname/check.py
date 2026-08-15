"""Check an Unison nickname through the restricted client."""

from src.lib.integrations.unison import NicknameCheck
from src.routes.lyrics._services import unison_client
from src.type_defs import RouteResponse

from .... import blueprint
from ..._forwarding import signed_envelope, unison_error_response, unison_response


@blueprint.route("/unison/auth/nickname/check", methods=["POST"])
def unison_nickname_check() -> RouteResponse:
    try:
        result = unison_client().check_nickname(NicknameCheck(signed_envelope()))
        return unison_response(result)
    except Exception as error:
        return unison_error_response(error)
