"""Forward a signed Unison lyric vote."""

from flask import request

from src.type_defs import RouteResponse

from .... import blueprint
from ..._forwarding import forward_signed_request


@blueprint.route("/unison/lyrics/<lyrics_id>/vote", methods=["POST", "DELETE"])
def unison_vote(lyrics_id: str) -> RouteResponse:
    return forward_signed_request(request.method, f"/lyrics/{lyrics_id}/vote")
