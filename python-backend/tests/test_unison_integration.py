import pytest
from src.lib.integrations.http import HttpTransportTimeout
from src.lib.integrations.unison import (
    HttpUnisonClient,
    NicknameCheck,
    NicknameCheckResult,
    NicknameUpdate,
    UnisonReport,
    UnisonResult,
    UnisonVote,
    UnisonVoteAction,
)
from src.lib.providers import (
    ProviderAuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)

from http_test_support import FakeHttpResponse, RecordingHttpTransport


class HttpUnisonClientTests:
    def test_known_operations_use_only_fixed_methods_and_paths(self) -> None:
        http = RecordingHttpTransport(
            *[FakeHttpResponse.json_response({"success": True}) for _ in range(6)]
        )
        client = HttpUnisonClient(http)
        envelope = {"payload": "signed", "signature": "value"}

        results = [
            client.vote("lyrics_1", UnisonVote(envelope)),
            client.vote(
                "lyrics_1",
                UnisonVote(envelope, action=UnisonVoteAction.REMOVE),
            ),
            client.report("lyrics_1", UnisonReport(envelope)),
            client.check_nickname(NicknameCheck(envelope)),
            client.update_nickname(NicknameUpdate(envelope)),
            client.update_nickname(NicknameUpdate(envelope, delete=True)),
        ]

        assert isinstance(results[0], UnisonResult)
        assert isinstance(results[3], NicknameCheckResult)
        assert [(call["method"], call["url"]) for call in http.calls] == [
            ("POST", "https://unison.boidu.dev/lyrics/lyrics_1/vote"),
            ("DELETE", "https://unison.boidu.dev/lyrics/lyrics_1/vote"),
            ("POST", "https://unison.boidu.dev/lyrics/lyrics_1/report"),
            ("POST", "https://unison.boidu.dev/auth/nickname/check"),
            ("PUT", "https://unison.boidu.dev/auth/nickname"),
            ("DELETE", "https://unison.boidu.dev/auth/nickname"),
        ]
        for call in http.calls:
            assert call["json"] == envelope
            assert call["headers"] == {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            assert call["allow_redirects"] is False
            assert "cookies" not in call and "auth" not in call

    @pytest.mark.parametrize(
        "identifier",
        ["", "../admin", "encoded%2Fpath", "space value", "x" * 129],
    )
    def test_invalid_identifiers_are_rejected_before_url_construction(
        self, identifier: str
    ) -> None:
        http = RecordingHttpTransport()

        with pytest.raises(ValueError):
            HttpUnisonClient(http).vote(identifier, UnisonVote({"signed": True}))

        assert http.calls == []

    def test_arbitrary_headers_and_urls_cannot_be_forwarded(self) -> None:
        http = RecordingHttpTransport(FakeHttpResponse.json_response({"ok": True}))
        malicious = {
            "url": "https://internal.example/admin",
            "headers": {"Cookie": "private", "Authorization": "secret"},
        }

        HttpUnisonClient(http).report("lyrics_1", UnisonReport(malicious))

        call = http.calls[0]
        assert call["url"] == "https://unison.boidu.dev/lyrics/lyrics_1/report"
        assert call["headers"] != malicious["headers"]
        assert "cookies" not in call

    @pytest.mark.parametrize(
        "response",
        [
            FakeHttpResponse(b"not-json", headers={"Content-Type": "application/json"}),
            FakeHttpResponse(b"<html></html>", headers={"Content-Type": "text/html"}),
            FakeHttpResponse(
                b"",
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(1024 * 1024 + 1),
                },
            ),
        ],
    )
    def test_malformed_or_oversized_upstream_payload_is_rejected(
        self, response: FakeHttpResponse
    ) -> None:
        client = HttpUnisonClient(RecordingHttpTransport(response))

        with pytest.raises(ProviderResponseError):
            client.report("lyrics_1", UnisonReport({"signed": True}))

        assert response.closed

    @pytest.mark.parametrize("status", [401, 403])
    def test_authentication_failures_are_translated(self, status: int) -> None:
        client = HttpUnisonClient(
            RecordingHttpTransport(
                FakeHttpResponse.json_response({"private": "error"}, status_code=status)
            )
        )

        with pytest.raises(ProviderAuthenticationError) as raised:
            client.vote("lyrics_1", UnisonVote({"signed": True}))

        assert "private" not in str(raised.value)

    def test_timeout_is_translated_without_signing_material(self) -> None:
        client = HttpUnisonClient(
            RecordingHttpTransport(error=HttpTransportTimeout("signature=private"))
        )

        with pytest.raises(ProviderUnavailableError) as raised:
            client.check_nickname(NicknameCheck({"signature": "private"}))

        assert "private" not in str(raised.value)

    def test_request_size_is_capped_before_network_access(self) -> None:
        http = RecordingHttpTransport()

        with pytest.raises(ValueError):
            HttpUnisonClient(http).report(
                "lyrics_1",
                UnisonReport({"payload": "x" * (64 * 1024)}),
            )

        assert http.calls == []
