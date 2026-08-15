"""Forward a validated signed Unison lyric vote."""

from flask import request

from src.lib.integrations.unison import UnisonVote, UnisonVoteAction
from src.routes.lyrics._services import unison_client
from src.type_defs import RouteResponse

from .... import blueprint
from ..._forwarding import signed_envelope, unison_error_response, unison_response


@blueprint.route("/unison/lyrics/<lyrics_id>/vote", methods=["POST", "DELETE"])
def unison_vote(lyrics_id: str) -> RouteResponse:
    try:
        action = UnisonVoteAction.REMOVE if request.method == "DELETE" else UnisonVoteAction.SUBMIT
        result = unison_client().vote(lyrics_id, UnisonVote(signed_envelope(), action))
        return unison_response(result)
    except Exception as error:
        return unison_error_response(error)
