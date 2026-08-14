"""LAN remote-control page."""

from flask import Response

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control


@blueprint.route("/remote")
def remote_page() -> RouteResponse:
    return Response(remote_control().page_html(), mimetype="text/html")
