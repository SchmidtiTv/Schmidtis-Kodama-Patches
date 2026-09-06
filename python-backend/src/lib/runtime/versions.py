"""Report installed backend dependency versions without loading their clients."""

import platform
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version


def backend_versions() -> dict[str, str]:
    """Return diagnostic versions, tolerating unavailable package metadata."""
    versions = {"python": platform.python_version()}
    for label, package in (("ytmusicapi", "ytmusicapi"), ("ytdlp", "yt-dlp")):
        try:
            versions[label] = version(package)
        except PackageNotFoundError:
            # Frozen builds can bundle a module without its distribution metadata.
            module_name = "yt_dlp.version" if label == "ytdlp" else "ytmusicapi"
            try:
                value = getattr(import_module(module_name), "__version__", "?")
            except ImportError:
                value = "?"
            versions[label] = value if isinstance(value, str) else "?"
    return versions
