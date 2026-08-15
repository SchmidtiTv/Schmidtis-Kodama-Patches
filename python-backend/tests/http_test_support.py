"""Deterministic HTTP doubles shared by integration-client tests."""

import json
from collections.abc import Iterator, Mapping

from src.lib.integrations.http import HttpResponse, HttpTransportError


class FakeHttpResponse:
    def __init__(
        self,
        content: bytes = b"",
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.content = content
        self.text = content.decode("utf-8", errors="replace")
        self._chunks = chunks
        self.closed = False

    @classmethod
    def json_response(
        cls,
        payload: object,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> "FakeHttpResponse":
        response_headers = {"Content-Type": "application/json"}
        response_headers.update(headers or {})
        return cls(
            json.dumps(payload).encode(),
            status_code=status_code,
            headers=response_headers,
        )

    def json(self) -> object:
        return json.loads(self.content)

    def iter_content(self, chunk_size: int = 65536) -> Iterator[bytes]:
        chunks = self._chunks if self._chunks is not None else [self.content]
        yield from chunks

    def close(self) -> None:
        self.closed = True


class RecordingHttpTransport:
    def __init__(
        self,
        *responses: HttpResponse,
        error: HttpTransportError | None = None,
    ) -> None:
        self.responses = list(responses)
        self.error = error
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **options: object) -> HttpResponse:
        self.calls.append({"method": method, "url": url, **options})
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("Unexpected HTTP request")
        return self.responses.pop(0)
