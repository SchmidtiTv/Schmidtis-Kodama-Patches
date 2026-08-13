"""Shared concrete types for backend boundaries."""

from flask import Response

type RouteResponse = Response | str | tuple[Response, int] | tuple[str, int] | tuple[
    bytes, int, dict[str, str]
]
