"""Clear one cache category or every cache category."""

import contextlib
from pathlib import Path

from flask import jsonify, request

from src.config import config_dirs
from src.lib import CacheSettings
from src.type_defs import RouteResponse

from . import blueprint
from ._services import download_service, metadata_cache, playlist_cache


@blueprint.route("/cache/clear", methods=["POST"])
def cache_clear() -> RouteResponse:
    directories = CacheSettings.category_directories(config_dirs)
    category = (request.get_json(silent=True) or {}).get("category", "all")
    categories = [category] if category in directories else list(directories)
    structured_cache = metadata_cache()
    for current_category in categories:
        if structured_cache is not None:
            structured_cache.clear(current_category)
            if current_category == "playlists":
                structured_cache.clear_audio_counterparts()
        try:
            paths = list(directories[current_category].iterdir())
        except OSError:
            paths: list[Path] = []
        for path in paths:
            with contextlib.suppress(OSError):
                path.unlink()
        if current_category == "playlists":
            playlist_cache().clear_memory()
        if current_category == "songs":
            download_service().status.clear()
    return jsonify({"ok": True})
