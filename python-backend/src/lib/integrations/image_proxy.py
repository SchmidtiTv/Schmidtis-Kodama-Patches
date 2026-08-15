"""SSRF-restricted image retrieval integration."""

import ipaddress
import re
import socket
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from src.lib.integrations.http import HttpResponse, HttpTransport, HttpTransportError
from src.lib.providers.errors import ProviderResponseError, ProviderUnavailableError


class ImageTargetRejectedError(ValueError):
    """The requested target is unsafe for server-side retrieval."""


@dataclass(frozen=True, slots=True)
class ImageSource:
    url: str


@dataclass(frozen=True, slots=True)
class ProxiedImage:
    content: bytes
    content_type: str
    cache_control: str | None


class ImageProxyClient(Protocol):
    def fetch(self, source: ImageSource) -> ProxiedImage: ...


class RestrictedImageProxyClient:
    _MAX_REDIRECTS = 3
    _MAX_IMAGE_BYTES = 8 * 1024 * 1024
    _TIMEOUT = (3.0, 7.0)
    _IMAGE_TYPES = frozenset({"image/avif", "image/gif", "image/jpeg", "image/png", "image/webp"})
    _REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
    _CACHE_CONTROL = re.compile(r"^(?:public,\s*)?max-age=(\d+)$", re.IGNORECASE)

    def __init__(
        self,
        http: HttpTransport,
        resolver: Callable[[str, int], Sequence[str]] | None = None,
    ) -> None:
        self._http = http
        self._resolver = resolver or self._resolve_addresses

    def fetch(self, source: ImageSource) -> ProxiedImage:
        current_url = source.url
        for redirect_count in range(self._MAX_REDIRECTS + 1):
            host = self._validate_target(current_url)
            try:
                response = self._http.request(
                    "GET",
                    current_url,
                    headers=self._headers(host),
                    timeout=self._TIMEOUT,
                    allow_redirects=False,
                    stream=True,
                )
            except HttpTransportError:
                raise ProviderUnavailableError() from None
            if response.status_code in self._REDIRECT_STATUSES:
                location = response.headers.get("Location")
                response.close()
                if not location or redirect_count >= self._MAX_REDIRECTS:
                    raise ProviderResponseError()
                current_url = urljoin(current_url, location)
                continue
            return self._image_response(response)
        raise ProviderResponseError()

    def _validate_target(self, url: str) -> str:
        if not isinstance(url, str) or len(url) > 4096:
            raise ImageTargetRejectedError("Image URL is invalid")
        try:
            parsed = urlsplit(url)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError:
            raise ImageTargetRejectedError("Image URL is invalid") from None
        if parsed.scheme not in ("http", "https"):
            raise ImageTargetRejectedError("Image URL scheme is forbidden")
        if parsed.username is not None or parsed.password is not None:
            raise ImageTargetRejectedError("Image URL credentials are forbidden")
        if not parsed.hostname:
            raise ImageTargetRejectedError("Image URL hostname is required")
        try:
            host = parsed.hostname.rstrip(".").encode("idna").decode("ascii")
        except UnicodeError:
            raise ImageTargetRejectedError("Image URL hostname is invalid") from None
        if not host or any(character.isspace() for character in host):
            raise ImageTargetRejectedError("Image URL hostname is invalid")
        try:
            addresses = self._resolver(host, port)
        except OSError:
            raise ProviderUnavailableError() from None
        if not addresses:
            raise ProviderUnavailableError()
        for address in addresses:
            try:
                parsed_address = ipaddress.ip_address(address)
            except ValueError:
                raise ImageTargetRejectedError("Image target address is invalid") from None
            if self._prohibited_address(parsed_address):
                raise ImageTargetRejectedError("Image target network is forbidden")
        return host

    def _image_response(self, response: HttpResponse) -> ProxiedImage:
        if response.status_code != 200:
            response.close()
            raise ProviderResponseError()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if content_type not in self._IMAGE_TYPES:
            response.close()
            raise ProviderResponseError()
        cache_control = self._safe_cache_control(response.headers)
        content = self._read_limited(response)
        return ProxiedImage(
            content=content,
            content_type=content_type,
            cache_control=cache_control,
        )

    @classmethod
    def _read_limited(cls, response: HttpResponse) -> bytes:
        raw_length = response.headers.get("Content-Length")
        if raw_length:
            try:
                if int(raw_length) > cls._MAX_IMAGE_BYTES:
                    response.close()
                    raise ProviderResponseError()
            except ValueError:
                response.close()
                raise ProviderResponseError() from None
        content = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=65536):
                content.extend(chunk)
                if len(content) > cls._MAX_IMAGE_BYTES:
                    raise ProviderResponseError()
        finally:
            response.close()
        return bytes(content)

    @classmethod
    def _safe_cache_control(cls, headers: Mapping[str, str]) -> str | None:
        value = headers.get("Cache-Control", "").strip()
        match = cls._CACHE_CONTROL.fullmatch(value)
        if match is None:
            return None
        seconds = min(int(match.group(1)), 604800)
        return f"public, max-age={seconds}"

    @staticmethod
    def _headers(host: str) -> dict[str, str]:
        headers = {
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif",
            "User-Agent": "Mozilla/5.0",
        }
        youtube_hosts = ("youtube.com", "ytimg.com", "yt3.ggpht.com")
        if any(host == domain or host.endswith(f".{domain}") for domain in youtube_hosts):
            headers["Referer"] = "https://music.youtube.com/"
        return headers

    @staticmethod
    def _prohibited_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
        )

    @staticmethod
    def _resolve_addresses(host: str, port: int) -> Sequence[str]:
        return tuple(
            sorted(
                {
                    str(address[4][0])
                    for address in socket.getaddrinfo(
                        host,
                        port,
                        type=socket.SOCK_STREAM,
                    )
                }
            )
        )
