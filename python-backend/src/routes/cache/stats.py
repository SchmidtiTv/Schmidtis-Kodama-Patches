"""Report cache size, item count, and enabled state by category."""

from flask import jsonify

from src.config import config_dirs
from src.lib import CacheSettings, DirectoryInspector
from src.type_defs import RouteResponse

from . import blueprint
from ._services import cache_settings, metadata_cache


@blueprint.route("/cache/stats")
def cache_stats() -> RouteResponse:
    directories = CacheSettings.category_directories(config_dirs)
    result = {}
    settings = cache_settings()
    structured_cache = metadata_cache()
    for category, directory in directories.items():
        size, count = DirectoryInspector.size_and_file_count(directory)
        if structured_cache is not None and category in {"playlists", "albums", "lyrics"}:
            database_size, database_count = structured_cache.stats(category)
            size += database_size
            count += database_count
            if category == "playlists":
                counterpart_size, counterpart_count = structured_cache.audio_counterpart_stats()
                size += counterpart_size
                count += counterpart_count
        if category == "songs":
            try:
                count = sum(path.suffix == ".json" for path in directory.iterdir())
            except OSError:
                count = 0
        result[category] = {"size": size, "count": count, "enabled": settings.enabled[category]}
    return jsonify(result)
