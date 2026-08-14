"""Synchronize desktop state and queued remote-control commands."""

from flask import jsonify, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import remote_control
from ._services import _is_local


@blueprint.route("/remote/_sync", methods=["POST"])
def remote_sync() -> RouteResponse:
    if not _is_local():
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"commands": remote_control().sync(request.json or {})})
