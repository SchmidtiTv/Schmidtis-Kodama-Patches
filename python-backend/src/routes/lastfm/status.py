"""Last.fm connection status endpoint."""

from flask import jsonify

from src.type_defs import RouteResponse

from . import blueprint
from ._services import lastfm_client, read_active_metadata


@blueprint.route("/status")
def lastfm_status() -> RouteResponse:
    metadata = read_active_metadata()
    return jsonify(
        {
            "enabled": lastfm_client().lastfm_enabled(),
            "connected": bool(metadata.get("lastfm_session")),
            "username": metadata.get("lastfm_user", ""),
        }
    )
