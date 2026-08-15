"""Minimal injectable transport boundary for external HTTP integrations."""

from collections.abc import Callable, Iterator, Mapping
from typing import Protocol, cast

import requests


class HttpResponse(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def content(self) -> bytes: ...

    @property
    def text(self) -> str: ...

    def json(self) -> object: ...

    def iter_content(self, chunk_size: int = 65536) -> Iterator[bytes]: ...

    def close(self) -> None: ...


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        **options: object,
    ) -> HttpResponse: ...


class HttpTransportError(Exception):
    """Safe base error for failures before an HTTP response is available."""


class HttpTransportTimeout(HttpTransportError):
    """The external request exceeded its configured timeout."""


class HttpTransportConnectionError(HttpTransportError):
    """The external request could not be completed."""


class RequestsHttpTransport:
    """Requests-backed implementation shared only during composition."""

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def request(self, method: str, url: str, **options: object) -> HttpResponse:
        try:
            request = cast("Callable[..., object]", self._session.request)
            return cast("HttpResponse", request(method, url, **options))
        except requests.Timeout:
            raise HttpTransportTimeout() from None
        except requests.RequestException:
            raise HttpTransportConnectionError() from None
