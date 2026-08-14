"""OBS overlay server-sent event stream."""

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import overlay_server


@blueprint.route("/overlay/stream")
def overlay_stream() -> RouteResponse:
    return overlay_server().stream_response()
