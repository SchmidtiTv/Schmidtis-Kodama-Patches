import json

import pytest
from src.lib.integrations.http import HttpTransportTimeout
from src.lib.music.credits import SongCreditsCache, SongCreditsService
from src.lib.providers import ProviderResponseError, ProviderUnavailableError, SongCredits
from src.lib.providers.youtube import YoutubeSongCreditsProvider

from http_test_support import FakeHttpResponse, RecordingHttpTransport


def _next_payload(description: str) -> dict[str, object]:
    return {
        "contents": {
            "twoColumnWatchNextResults": {
                "results": {
                    "results": {
                        "contents": [
                            {
                                "videoSecondaryInfoRenderer": {
                                    "attributedDescription": {"content": description}
                                }
                            }
                        ]
                    }
                }
            }
        }
    }


class YoutubeSongCreditsProviderTests:
    def test_innertube_success_is_normalized_without_fallback(self) -> None:
        response = FakeHttpResponse.json_response(_next_payload("  credits text  "))
        http = RecordingHttpTransport(response)

        result = YoutubeSongCreditsProvider(http).get_credits("video_1")

        assert result == SongCredits(description="credits text")
        assert len(http.calls) == 1
        assert http.calls[0]["method"] == "POST"
        assert http.calls[0]["allow_redirects"] is False
        assert response.closed

    def test_watch_page_fallback_parses_player_response_defensively(self) -> None:
        empty = FakeHttpResponse.json_response({})
        player = {"videoDetails": {"shortDescription": "  HTML credits  "}}
        html = f"<script>ytInitialPlayerResponse = {json.dumps(player)};</script>"
        fallback = FakeHttpResponse(
            html.encode(),
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        http = RecordingHttpTransport(empty, fallback)

        assert YoutubeSongCreditsProvider(http).get_credits("video_1") == SongCredits(
            "HTML credits"
        )
        assert [call["method"] for call in http.calls] == ["POST", "GET"]
        assert http.calls[1]["params"] == {"v": "video_1"}

    def test_valid_missing_description_returns_normalized_empty_result(self) -> None:
        empty = FakeHttpResponse.json_response({})
        html = b'<script>ytInitialPlayerResponse={"videoDetails":{}};</script>'
        fallback = FakeHttpResponse(html, headers={"Content-Type": "text/html"})

        result = YoutubeSongCreditsProvider(RecordingHttpTransport(empty, fallback)).get_credits(
            "video_1"
        )

        assert result == SongCredits("")

    @pytest.mark.parametrize(
        "fallback_html",
        [b"<html>missing player data</html>", b"ytInitialPlayerResponse = {bad json"],
    )
    def test_malformed_json_and_player_html_are_safe_errors(self, fallback_html: bytes) -> None:
        malformed = FakeHttpResponse(b"not-json", headers={"Content-Type": "application/json"})
        fallback = FakeHttpResponse(
            fallback_html,
            headers={"Content-Type": "text/html"},
        )

        with pytest.raises(ProviderResponseError) as raised:
            YoutubeSongCreditsProvider(RecordingHttpTransport(malformed, fallback)).get_credits(
                "video_1"
            )

        assert str(raised.value) == "Provider returned an invalid response."

    def test_oversized_responses_are_rejected_and_closed(self) -> None:
        oversized = FakeHttpResponse(
            b"",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(1024 * 1024 + 1),
            },
        )
        fallback = FakeHttpResponse(
            b"",
            headers={
                "Content-Type": "text/html",
                "Content-Length": str(2 * 1024 * 1024 + 1),
            },
        )

        with pytest.raises(ProviderResponseError):
            YoutubeSongCreditsProvider(RecordingHttpTransport(oversized, fallback)).get_credits(
                "video_1"
            )

        assert oversized.closed and fallback.closed

    def test_transport_timeout_is_safe_and_does_not_expose_details(self) -> None:
        provider = YoutubeSongCreditsProvider(
            RecordingHttpTransport(error=HttpTransportTimeout("private upstream"))
        )

        with pytest.raises(ProviderUnavailableError) as raised:
            provider.get_credits("video_1")

        assert "private upstream" not in str(raised.value)


class SongCreditsServiceTests:
    def test_success_is_cached_and_avoids_a_second_provider_call(self) -> None:
        provider = FakeCreditsProvider(SongCredits("credits"))
        service = SongCreditsService(provider, SongCreditsCache())

        assert service.get_credits("video_1") == SongCredits("credits")
        assert service.get_credits("video_1") == SongCredits("credits")
        assert provider.calls == ["video_1"]

    def test_transient_failure_is_not_cached(self) -> None:
        provider = FakeCreditsProvider(error=ProviderUnavailableError())
        service = SongCreditsService(provider, SongCreditsCache())

        with pytest.raises(ProviderUnavailableError):
            service.get_credits("video_1")
        with pytest.raises(ProviderUnavailableError):
            service.get_credits("video_1")

        assert provider.calls == ["video_1", "video_1"]


class FakeCreditsProvider:
    def __init__(
        self,
        result: SongCredits | None = None,
        *,
        error: ProviderUnavailableError | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    def get_credits(self, video_id: str) -> SongCredits:
        self.calls.append(video_id)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result
