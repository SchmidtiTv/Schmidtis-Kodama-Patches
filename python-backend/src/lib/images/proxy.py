"""Cache orchestration for restricted image proxy retrieval."""

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from src.lib.integrations.image_proxy import ImageProxyClient, ImageSource, ProxiedImage
from src.lib.music.youtube_data import YoutubeResponseMapper
from src.lib.runtime.cache import CacheSettings


@dataclass(frozen=True, slots=True)
class ImageProxyResult:
    image: ProxiedImage
    cache_hit: bool


class ImageProxyService:
    _EXTENSIONS: ClassVar[dict[str, str]] = {
        "image/avif": "avif",
        "image/gif": "gif",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }

    def __init__(
        self,
        client: ImageProxyClient,
        cache_settings: CacheSettings,
        cache_directory: Path,
        cache_ttl: int,
    ) -> None:
        self._client = client
        self._cache_settings = cache_settings
        self._cache_directory = cache_directory
        self._cache_ttl = cache_ttl

    def fetch(self, url: str, *, high_quality: bool = False) -> ImageProxyResult:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("Image URL required")
        normalized_url = (
            YoutubeResponseMapper.upscale_thumbnail_url(url.strip())
            if high_quality
            else url.strip()
        )
        cache_key = hashlib.sha256(normalized_url.encode()).hexdigest()
        if self._cache_settings.enabled["images"]:
            cached = self._cached_image(cache_key)
            if cached is not None:
                return ImageProxyResult(cached, True)
        image = self._client.fetch(ImageSource(normalized_url))
        if self._cache_settings.enabled["images"]:
            extension = self._EXTENSIONS[image.content_type]
            (self._cache_directory / f"{cache_key}.{extension}").write_bytes(image.content)
        return ImageProxyResult(image, False)

    def _cached_image(self, cache_key: str) -> ProxiedImage | None:
        for content_type, extension in self._EXTENSIONS.items():
            path = self._cache_directory / f"{cache_key}.{extension}"
            try:
                if not path.is_file() or time.time() - path.stat().st_mtime >= self._cache_ttl:
                    continue
                return ProxiedImage(
                    content=path.read_bytes(),
                    content_type=content_type,
                    cache_control="public, max-age=604800",
                )
            except OSError:
                continue
        return None
