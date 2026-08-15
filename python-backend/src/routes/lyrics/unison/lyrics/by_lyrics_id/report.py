"""Forward a validated signed Unison lyric report."""

from src.lib.integrations.unison import UnisonReport
from src.routes.lyrics._services import unison_client
from src.type_defs import RouteResponse

from .... import blueprint
from ..._forwarding import signed_envelope, unison_error_response, unison_response


@blueprint.route("/unison/lyrics/<lyrics_id>/report", methods=["POST"])
def unison_report(lyrics_id: str) -> RouteResponse:
    try:
        result = unison_client().report(lyrics_id, UnisonReport(signed_envelope()))
        return unison_response(result)
    except Exception as error:
        return unison_error_response(error)
