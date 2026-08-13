"""Forward signed Unison nickname changes."""

from flask import request

from src.type_defs import RouteResponse

from . import blueprint
from ._unison import forward_signed_request


@blueprint.route("/unison/auth/nickname", methods=["PUT", "DELETE"])
def unison_nickname() -> RouteResponse:
    return forward_signed_request(request.method, "/auth/nickname")
