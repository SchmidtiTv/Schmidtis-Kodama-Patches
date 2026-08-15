from collections.abc import Iterator
from unittest.mock import patch

import pytest
from src.lib.integrations.http import (
    HttpResponse,
    HttpTransportConnectionError,
    HttpTransportError,
    HttpTransportTimeout,
)
from src.lib.music.song_statistics import SongStatisticsService
from src.lib.providers import (
    ProviderResponseError,
    ProviderUnavailableError,
    ReturnYoutubeDislikeProvider,
    SongStatistics,
    SongStatisticsProvider,
)


class FakeResponse:
    def __init__(
        self,
        payload: object = None,
        *,
        status_code: int = 200,
        json_error: ValueError | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        self.content = b""
        self.text = ""
        self.payload = payload
        self.json_error = json_error
        self.json_calls = 0

    def json(self) -> object:
        self.json_calls += 1
        if self.json_error is not None:
            raise self.json_error
        return self.payload

    def iter_content(self, chunk_size: int = 65536) -> Iterator[bytes]:
        yield self.content

    def close(self) -> None:
        return None


class FakeHttpTransport:
    def __init__(
        self,
        response: HttpResponse | None = None,
        error: HttpTransportError | None = None,
    ) -> None:
        self.response = response or FakeResponse({})
        self.error = error
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **options: object) -> HttpResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                **options,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


class FakeStatisticsProvider:
    def __init__(self, statistics: SongStatistics) -> None:
        self.statistics = statistics
        self.video_ids: list[str] = []

    def get_statistics(self, video_id: str) -> SongStatistics:
        self.video_ids.append(video_id)
        return self.statistics


class ReturnYoutubeDislikeProviderTests:
    def test_valid_response_is_normalized_and_request_is_owned_by_provider(self) -> None:
        http = FakeHttpTransport(
            FakeResponse({"viewCount": 1_500_000, "likes": 20_000, "dislikes": 1_500})
        )
        provider: SongStatisticsProvider = ReturnYoutubeDislikeProvider(http=http)

        statistics = provider.get_statistics("video-id")

        assert statistics == SongStatistics(views=1_500_000, likes=20_000, dislikes=1_500)
        assert http.calls == [
            {
                "url": "https://returnyoutubedislikeapi.com/votes",
                "method": "GET",
                "params": {"videoId": "video-id"},
                "headers": {"Accept": "application/json"},
                "timeout": 5.0,
            }
        ]

    def test_missing_and_null_counters_are_normalized_to_none(self) -> None:
        provider = ReturnYoutubeDislikeProvider(
            http=FakeHttpTransport(FakeResponse({"viewCount": None, "likes": 12}))
        )

        assert provider.get_statistics("video-id") == SongStatistics(
            views=None,
            likes=12,
            dislikes=None,
        )

    @pytest.mark.parametrize("value", [True, False, "12", 12.5, [], {}, -1])
    def test_invalid_counter_types_and_values_are_rejected(self, value: object) -> None:
        provider = ReturnYoutubeDislikeProvider(
            http=FakeHttpTransport(FakeResponse({"viewCount": value}))
        )

        with pytest.raises(ProviderResponseError):
            provider.get_statistics("video-id")

    @pytest.mark.parametrize("payload", [None, [], "response", 123, True])
    def test_non_object_json_is_rejected(self, payload: object) -> None:
        provider = ReturnYoutubeDislikeProvider(http=FakeHttpTransport(FakeResponse(payload)))

        with pytest.raises(ProviderResponseError):
            provider.get_statistics("video-id")

    def test_malformed_json_becomes_a_safe_response_error(self) -> None:
        provider = ReturnYoutubeDislikeProvider(
            http=FakeHttpTransport(
                FakeResponse(json_error=ValueError("raw body with secret-token"))
            )
        )

        with pytest.raises(ProviderResponseError) as raised:
            provider.get_statistics("video-id")

        assert str(raised.value) == "Provider returned an invalid response."
        assert "secret-token" not in str(raised.value)

    def test_non_success_status_is_rejected_without_parsing_the_body(self) -> None:
        response = FakeResponse({"secret": "raw upstream body"}, status_code=503)
        provider = ReturnYoutubeDislikeProvider(http=FakeHttpTransport(response))

        with pytest.raises(ProviderResponseError):
            provider.get_statistics("video-id")

        assert response.json_calls == 0

    @pytest.mark.parametrize(
        "failure",
        [HttpTransportTimeout(), HttpTransportConnectionError()],
    )
    def test_request_failures_become_safe_unavailable_errors(
        self, failure: HttpTransportError
    ) -> None:
        provider = ReturnYoutubeDislikeProvider(http=FakeHttpTransport(error=failure))

        with pytest.raises(ProviderUnavailableError) as raised:
            provider.get_statistics("video-id")

        assert str(raised.value) == "Provider is unavailable."
        assert "secret" not in str(raised.value)

    def test_injected_transport_prevents_real_network_access(self) -> None:
        provider = ReturnYoutubeDislikeProvider(http=FakeHttpTransport(FakeResponse({})))

        with patch("requests.Session.request") as network_request:
            provider.get_statistics("video-id")

        network_request.assert_not_called()


class SongStatisticsServiceTests:
    @pytest.mark.parametrize(
        ("count", "formatted"),
        [
            (999, "999"),
            (1_000, "1.0K"),
            (1_500, "1.5K"),
            (999_999, "1000.0K"),
            (1_000_000, "1.0M"),
            (1_500_000, "1.5M"),
            (None, None),
        ],
    )
    def test_k_and_m_formatting_boundaries(self, count: int | None, formatted: str | None) -> None:
        service = SongStatisticsService(
            FakeStatisticsProvider(SongStatistics(views=count, likes=None, dislikes=None))
        )

        assert service.get_statistics("video-id")["views"] == formatted

    def test_success_shape_is_preserved_exactly(self) -> None:
        provider = FakeStatisticsProvider(
            SongStatistics(views=1_500_000, likes=20_000, dislikes=1_500)
        )
        service = SongStatisticsService(provider)

        assert service.get_statistics("video-id") == {
            "views": "1.5M",
            "likes": "20.0K",
            "dislikes": "1.5K",
            "viewsRaw": 1_500_000,
            "likesRaw": 20_000,
            "dislikesRaw": 1_500,
        }
        assert provider.video_ids == ["video-id"]
