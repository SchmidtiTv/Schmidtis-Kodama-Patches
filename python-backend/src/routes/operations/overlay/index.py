"""OBS overlay preview page."""

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import overlay_server


@blueprint.route("/overlay")
def overlay_page() -> RouteResponse:
    return overlay_server().page_response()
