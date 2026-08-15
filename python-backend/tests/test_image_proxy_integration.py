from collections.abc import Sequence
from pathlib import Path

import pytest
from src.lib.images import ImageProxyService
from src.lib.integrations.image_proxy import (
    ImageSource,
    ImageTargetRejectedError,
    ProxiedImage,
    RestrictedImageProxyClient,
)
from src.lib.providers import ProviderResponseError
from src.lib.runtime.cache import CacheSettings

from http_test_support import FakeHttpResponse, RecordingHttpTransport

PUBLIC_IP = "93.184.216.34"


def _public_resolver(host: str, port: int) -> Sequence[str]:
    del host, port
    return [PUBLIC_IP]


class RestrictedImageProxyClientTests:
    def test_valid_image_is_bounded_and_headers_are_sanitized(self) -> None:
        upstream = FakeHttpResponse(
            b"jpeg-content",
            headers={
                "Content-Type": "image/jpeg; charset=binary",
                "Cache-Control": "public, max-age=9999999",
                "Set-Cookie": "private=session",
                "Access-Control-Allow-Origin": "*",
                "Location": "https://internal.example/",
            },
        )
        http = RecordingHttpTransport(upstream)

        image = RestrictedImageProxyClient(http, _public_resolver).fetch(
            ImageSource("https://images.example/cover.jpg")
        )

        assert image == ProxiedImage(
            content=b"jpeg-content",
            content_type="image/jpeg",
            cache_control="public, max-age=604800",
        )
        assert upstream.closed
        assert http.calls[0]["allow_redirects"] is False
        assert http.calls[0]["stream"] is True
        request_headers = http.calls[0]["headers"]
        assert isinstance(request_headers, dict)
        assert "Cookie" not in request_headers

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://images.example/cover.jpg",
            "https://user:password@images.example/cover.jpg",
            "https://",
            "https://images.example:99999/cover.jpg",
        ],
    )
    def test_invalid_schemes_credentials_hosts_and_ports_are_rejected(self, url: str) -> None:
        http = RecordingHttpTransport()

        with pytest.raises(ImageTargetRejectedError):
            RestrictedImageProxyClient(http, _public_resolver).fetch(ImageSource(url))

        assert http.calls == []

    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "10.0.0.8",
            "169.254.169.254",
            "0.0.0.0",
            "224.0.0.1",
            "::1",
            "fc00::1",
        ],
    )
    def test_prohibited_literal_and_dns_resolved_addresses_are_rejected(self, address: str) -> None:
        http = RecordingHttpTransport()

        with pytest.raises(ImageTargetRejectedError):
            RestrictedImageProxyClient(http, lambda host, port: [address]).fetch(
                ImageSource("https://images.example/cover.jpg")
            )

        assert http.calls == []

    def test_redirect_target_is_resolved_and_rejected_before_following(self) -> None:
        redirect = FakeHttpResponse(
            status_code=302,
            headers={"Location": "http://metadata.internal/latest"},
        )
        http = RecordingHttpTransport(redirect)

        def resolver(host: str, port: int) -> Sequence[str]:
            del port
            return ["169.254.169.254"] if host == "metadata.internal" else [PUBLIC_IP]

        with pytest.raises(ImageTargetRejectedError):
            RestrictedImageProxyClient(http, resolver).fetch(
                ImageSource("https://images.example/start")
            )

        assert len(http.calls) == 1
        assert redirect.closed

    def test_excessive_redirects_are_rejected_at_the_small_limit(self) -> None:
        responses = [
            FakeHttpResponse(status_code=302, headers={"Location": f"/hop-{index}"})
            for index in range(4)
        ]
        http = RecordingHttpTransport(*responses)

        with pytest.raises(ProviderResponseError):
            RestrictedImageProxyClient(http, _public_resolver).fetch(
                ImageSource("https://images.example/start")
            )

        assert len(http.calls) == 4
        assert all(response.closed for response in responses)

    def test_oversized_body_is_rejected_and_closed(self) -> None:
        response = FakeHttpResponse(
            b"",
            headers={
                "Content-Type": "image/png",
                "Content-Length": str(8 * 1024 * 1024 + 1),
            },
        )

        with pytest.raises(ProviderResponseError):
            RestrictedImageProxyClient(RecordingHttpTransport(response), _public_resolver).fetch(
                ImageSource("https://images.example/cover.png")
            )

        assert response.closed

    @pytest.mark.parametrize("content_type", ["text/html", "application/octet-stream", ""])
    def test_html_and_ambiguous_content_types_are_rejected(self, content_type: str) -> None:
        response = FakeHttpResponse(b"body", headers={"Content-Type": content_type})

        with pytest.raises(ProviderResponseError):
            RestrictedImageProxyClient(RecordingHttpTransport(response), _public_resolver).fetch(
                ImageSource("https://images.example/cover")
            )

        assert response.closed

    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            ("max-age=120", "public, max-age=120"),
            ("private, max-age=120", None),
            ("no-store", None),
            ("public, max-age=invalid", None),
        ],
    )
    def test_only_safe_cache_control_is_returned(self, header: str, expected: str | None) -> None:
        response = FakeHttpResponse(
            b"image",
            headers={"Content-Type": "image/webp", "Cache-Control": header},
        )

        image = RestrictedImageProxyClient(
            RecordingHttpTransport(response), _public_resolver
        ).fetch(ImageSource("https://images.example/cover.webp"))

        assert image.cache_control == expected


class FakeImageClient:
    def __init__(
        self,
        image: ProxiedImage | None = None,
        error: ProviderResponseError | None = None,
    ) -> None:
        self.image = image
        self.error = error
        self.calls: list[ImageSource] = []

    def fetch(self, source: ImageSource) -> ProxiedImage:
        self.calls.append(source)
        if self.error is not None:
            raise self.error
        assert self.image is not None
        return self.image


class ImageProxyServiceTests:
    def test_success_is_cached_only_after_client_returns(self, tmp_path: Path) -> None:
        client = FakeImageClient(ProxiedImage(b"image", "image/png", None))
        service = ImageProxyService(
            client,
            CacheSettings(defaults={"images": True}),
            tmp_path,
            cache_ttl=60,
        )

        first = service.fetch("https://images.example/cover.png")
        second = service.fetch("https://images.example/cover.png")

        assert not first.cache_hit
        assert second.cache_hit
        assert second.image.content == b"image"
        assert client.calls == [ImageSource("https://images.example/cover.png")]

    def test_failed_fetch_does_not_leave_a_partial_cache_entry(self, tmp_path: Path) -> None:
        client = FakeImageClient(error=ProviderResponseError())
        service = ImageProxyService(
            client,
            CacheSettings(defaults={"images": True}),
            tmp_path,
            cache_ttl=60,
        )

        with pytest.raises(ProviderResponseError):
            service.fetch("https://images.example/cover.png")

        assert list(tmp_path.iterdir()) == []
