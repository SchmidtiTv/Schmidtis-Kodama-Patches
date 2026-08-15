"""Restricted client for known Unison signed-envelope operations."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from src.lib.integrations.http import HttpResponse, HttpTransport, HttpTransportError
from src.lib.providers.errors import (
    ProviderAuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)


class UnisonVoteAction(StrEnum):
    SUBMIT = "submit"
    REMOVE = "remove"


@dataclass(frozen=True, slots=True)
class UnisonVote:
    payload: Mapping[str, object]
    action: UnisonVoteAction = UnisonVoteAction.SUBMIT


@dataclass(frozen=True, slots=True)
class UnisonReport:
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class NicknameCheck:
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class NicknameUpdate:
    payload: Mapping[str, object]
    delete: bool = False


@dataclass(frozen=True, slots=True)
class UnisonResult:
    payload: object
    status_code: int


@dataclass(frozen=True, slots=True)
class NicknameCheckResult:
    payload: object
    status_code: int


class UnisonClient(Protocol):
    def vote(self, lyrics_id: str, request: UnisonVote) -> UnisonResult: ...

    def report(self, lyrics_id: str, request: UnisonReport) -> UnisonResult: ...

    def check_nickname(self, request: NicknameCheck) -> NicknameCheckResult: ...

    def update_nickname(self, request: NicknameUpdate) -> UnisonResult: ...


class HttpUnisonClient:
    _BASE_URL = "https://unison.boidu.dev"
    _IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
    _MAX_REQUEST_BYTES = 64 * 1024
    _MAX_RESPONSE_BYTES = 1 * 1024 * 1024

    def __init__(self, http: HttpTransport) -> None:
        self._http = http

    def vote(self, lyrics_id: str, request: UnisonVote) -> UnisonResult:
        self._validate_identifier(lyrics_id)
        method = "DELETE" if request.action is UnisonVoteAction.REMOVE else "POST"
        return self._send(method, f"/lyrics/{lyrics_id}/vote", request.payload)

    def report(self, lyrics_id: str, request: UnisonReport) -> UnisonResult:
        self._validate_identifier(lyrics_id)
        return self._send("POST", f"/lyrics/{lyrics_id}/report", request.payload)

    def check_nickname(self, request: NicknameCheck) -> NicknameCheckResult:
        result = self._send("POST", "/auth/nickname/check", request.payload)
        return NicknameCheckResult(result.payload, result.status_code)

    def update_nickname(self, request: NicknameUpdate) -> UnisonResult:
        return self._send("DELETE" if request.delete else "PUT", "/auth/nickname", request.payload)

    def _send(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object],
    ) -> UnisonResult:
        if not isinstance(payload, Mapping):
            raise ValueError("Signed Unison envelope must be an object")
        try:
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("Signed Unison envelope is invalid") from None
        if len(encoded) > self._MAX_REQUEST_BYTES:
            raise ValueError("Signed Unison envelope is too large")
        try:
            response = self._http.request(
                method,
                f"{self._BASE_URL}{path}",
                json=dict(payload),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=(4.0, 8.0),
                allow_redirects=False,
                stream=True,
            )
        except HttpTransportError:
            raise ProviderUnavailableError() from None
        if response.status_code in (401, 403):
            response.close()
            raise ProviderAuthenticationError()
        if response.status_code >= 500:
            response.close()
            raise ProviderUnavailableError()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if content_type != "application/json":
            response.close()
            raise ProviderResponseError()
        status_code = response.status_code
        content = self._read_limited(response)
        try:
            normalized = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProviderResponseError() from None
        return UnisonResult(normalized, status_code)

    @classmethod
    def _read_limited(cls, response: HttpResponse) -> bytes:
        try:
            raw_length = response.headers.get("Content-Length")
            if raw_length:
                try:
                    if int(raw_length) > cls._MAX_RESPONSE_BYTES:
                        raise ProviderResponseError()
                except ValueError:
                    raise ProviderResponseError() from None
            content = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                content.extend(chunk)
                if len(content) > cls._MAX_RESPONSE_BYTES:
                    raise ProviderResponseError()
            return bytes(content)
        finally:
            response.close()

    @classmethod
    def _validate_identifier(cls, value: str) -> None:
        if not cls._IDENTIFIER.fullmatch(value):
            raise ValueError("Invalid Unison identifier")
