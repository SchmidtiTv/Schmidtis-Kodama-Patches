"""HTTP response decoration shared by Composer Bridge endpoints."""

from collections.abc import Mapping
from urllib.parse import quote

from flask import Response

from src.config import config_composer
from src.lib import ComposerBridge


def bridge_headers(response: Response) -> Response:
    response.headers["Access-Control-Allow-Origin"] = config_composer.ORIGIN
    response.headers["Access-Control-Expose-Headers"] = ComposerBridge.EXPOSED_HEADERS
    return response


def bridge_headers_with_metadata(response: Response, metadata: Mapping[str, object]) -> Response:
    bridge_headers(response)
    title = metadata.get("title")
    if isinstance(title, str) and title:
        response.headers["x-track-title"] = quote(title)
    artist = metadata.get("artist")
    if isinstance(artist, str) and artist:
        response.headers["x-track-artist"] = quote(artist)
    return response
