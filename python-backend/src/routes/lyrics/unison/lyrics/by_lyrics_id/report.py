"""Forward a signed Unison lyric report."""

from src.type_defs import RouteResponse

from .... import blueprint
from ..._forwarding import forward_signed_request


@blueprint.route("/unison/lyrics/<lyrics_id>/report", methods=["POST"])
def unison_report(lyrics_id: str) -> RouteResponse:
    return forward_signed_request("POST", f"/lyrics/{lyrics_id}/report")
