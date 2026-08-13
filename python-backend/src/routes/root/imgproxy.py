"""Proxy thumbnail images with the configured persistent image cache."""

import hashlib
import time

import requests
from flask import Response, jsonify, request

from src.config import Config, config_dirs
from src.lib import YoutubeResponseMapper
from src.type_defs import RouteResponse

from . import blueprint
from ._services import cache_settings


@blueprint.route("/imgproxy")
def img_proxy() -> RouteResponse:
    url = request.args.get("url", "")
    if not url:
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
        content_type = "image/webp" if extension == "webp" else f"image/{extension}"
        response = Response(cache_path.read_bytes(), content_type=content_type)
        response.headers["Cache-Control"] = "public, max-age=604800"
        response.headers["X-Cache"] = "HIT"
        return response

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if "ytimg.com" in url or "yt3.ggpht.com" in url or "youtube.com" in url:
            headers["Referer"] = "https://music.youtube.com/"
        upstream = requests.get(url, headers=headers, timeout=10)
        upstream.raise_for_status()
        if image_cache_enabled:
            cache_path.write_bytes(upstream.content)
        response = Response(
            upstream.content, content_type=upstream.headers.get("Content-Type", "image/jpeg")
        )
        response.headers["Cache-Control"] = "public, max-age=604800"
        response.headers["X-Cache"] = "MISS"
        return response
    except Exception as error:
        return jsonify({"error": str(error)}), 500
