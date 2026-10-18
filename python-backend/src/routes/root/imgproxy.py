"""Proxy thumbnail images with the configured persistent image cache."""

import hashlib
import time
from urllib.parse import urlsplit

import requests
from flask import Response, jsonify, request

from src.config import Config, config_dirs
from src.lib import YoutubeResponseMapper

from . import blueprint
from ._services import cache_settings
from src.type_defs import RouteResponse

# Raster formats only, recognised by their signature rather than the upstream Content-Type:
# the proxy answers on the backend's own origin, so anything a browser would render as a
# document (HTML, or SVG with its scripts) would run with full API access, and CDNs label
# real images inconsistently (image/jpg, application/octet-stream, nothing at all).
_MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _image_type(body: bytes) -> str | None:
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if body.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    if body[4:12] in (b"ftypavif", b"ftypavis"):
        return "image/avif"
    return None


def _image_response(content: bytes, content_type: str, cache_state: str) -> Response:
    response = Response(content, content_type=content_type)
    response.headers["Cache-Control"] = "public, max-age=604800"
    response.headers["X-Cache"] = cache_state
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return response


def _download(url: str, headers: dict[str, str]) -> tuple[bytes, str] | None:
    """Fetch an image body and its type; None when it is not an image or too large."""
    with requests.get(url, headers=headers, timeout=10, stream=True) as upstream:
        upstream.raise_for_status()
        body = bytearray()
        for chunk in upstream.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > _MAX_IMAGE_BYTES:
                return None
    content_type = _image_type(bytes(body))
    return (bytes(body), content_type) if content_type else None


@blueprint.route("/imgproxy")
def img_proxy() -> RouteResponse:
    url = request.args.get("url", "")
    if urlsplit(url).scheme not in ("http", "https"):
        return "", 400
    if request.args.get("hq", "0") == "1":
        url = YoutubeResponseMapper.upscale_thumbnail_url(url)

    url_hash = hashlib.sha1(url.encode()).hexdigest()
    extension = next(
        (candidate for candidate in ("webp", "png", "gif") if candidate in url.lower()), "jpg"
    )
    cache_path = config_dirs.IMG_CACHE_DIR / f"{url_hash}.{extension}"
    image_cache_enabled = cache_settings().enabled["images"]
    if (
        image_cache_enabled
        and cache_path.exists()
        and time.time() - cache_path.stat().st_mtime < Config.IMG_CACHE_TTL
    ):
        cached = cache_path.read_bytes()
        cached_type = _image_type(cached)
        if cached_type:
            return _image_response(cached, cached_type, "HIT")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if "ytimg.com" in url or "yt3.ggpht.com" in url or "youtube.com" in url:
            headers["Referer"] = "https://music.youtube.com/"
        image = _download(url, headers)
        if image is None:
            return jsonify({"error": "not an image"}), 415
        content, content_type = image
        if image_cache_enabled:
            cache_path.write_bytes(content)
        return _image_response(content, content_type, "MISS")
    except Exception as error:
        return jsonify({"error": str(error)}), 500
