import threading
from unittest.mock import MagicMock, call, patch

from src.config import config_ytdlp
from src.lib.music.stream import StreamService


class StreamServiceTests:
    def setup_method(self) -> None:
        self.service = StreamService(MagicMock())

    def test_uses_fast_anonymous_www_resolution_before_music_client_retries(self) -> None:
        with (
            patch.object(
                self.service, "_browser_cookie_data", return_value="cookies"
            ) as cookie_data,
            patch.object(
                self.service, "_extract_url", return_value={"url": "https://stream/audio"}
            ) as extract,
            patch.object(self.service, "_probe_audio_url", return_value=True) as probe,
        ):
            payload, status = self.service.resolve_stream("video")

        assert (payload, status) == ({"url": "https://stream/audio"}, 200)
        extract.assert_called_once_with(
            "video",
            config_ytdlp.AUDIO_FORMAT,
            skip_auth=True,
            use_ytm=False,
        )
        cookie_data.assert_not_called()
        probe.assert_called_once_with("video", "https://stream/audio")

    def test_rejected_media_url_falls_through_to_cookie_resolution(self) -> None:
        with (
            patch.object(self.service, "_browser_cookie_data", return_value="cookies"),
            patch.object(
                self.service,
                "_extract_url",
                side_effect=[
                    {"url": "https://stream/rejected"},
                    {"url": "https://stream/working"},
                ],
            ) as extract,
            patch.object(self.service, "_probe_audio_url", side_effect=[False, True]) as probe,
        ):
            payload, status = self.service.resolve_stream("video")

        assert (payload, status) == ({"url": "https://stream/working"}, 200)
        cookie_stream = extract.call_args_list[1].kwargs["extra_opts"]["cookiefile"]
        assert cookie_stream.getvalue() == "cookies"
        assert probe.call_args_list == [
            call("video", "https://stream/rejected"),
            call("video", "https://stream/working"),
        ]

    def test_stream_resolution_is_serialized_across_video_ids(self) -> None:
        first_started = threading.Event()
        release_first = threading.Event()
        second_started = threading.Event()
        call_count = 0
        count_lock = threading.Lock()
        responses = []

        def extract(video_id: str, *_args: object, **_kwargs: object) -> dict[str, str]:
            nonlocal call_count
            with count_lock:
                call_count += 1
                current_call = call_count
            if current_call == 1:
                first_started.set()
                assert release_first.wait(timeout=2)
            else:
                second_started.set()
            return {"url": f"https://stream/{video_id}"}

        with (
            patch.object(self.service, "_extract_url", side_effect=extract),
            patch.object(self.service, "_probe_audio_url", return_value=True),
        ):
            first = threading.Thread(
                target=lambda: responses.append(self.service.resolve_stream("first"))
            )
            second = threading.Thread(
                target=lambda: responses.append(self.service.resolve_stream("second"))
            )
            first.start()
            assert first_started.wait(timeout=2)
            second.start()
            assert not second_started.wait(timeout=0.1)
            release_first.set()
            first.join(timeout=2)
            second.join(timeout=2)

        assert second_started.is_set()
        assert sorted(responses, key=lambda response: str(response[0]["url"])) == [
            ({"url": "https://stream/first"}, 200),
            ({"url": "https://stream/second"}, 200),
        ]

    def test_concurrent_audio_resolution_runs_one_stream_request(self) -> None:
        started = threading.Event()
        release = threading.Event()
        responses = []

        class Response:
            @staticmethod
            def json() -> dict[str, str]:
                return {"url": "https://stream/audio"}

        def get(*_args: object, **_kwargs: object) -> Response:
            started.set()
            assert release.wait(timeout=2)
            return Response()

        with patch("src.lib.music.stream.requests.get", side_effect=get) as request_get:
            first = threading.Thread(
                target=lambda: responses.append(self.service.resolve_audio_url("video"))
            )
            second = threading.Thread(
                target=lambda: responses.append(self.service.resolve_audio_url("video"))
            )
            first.start()
            assert started.wait(timeout=2)
            second.start()
            release.set()
            first.join(timeout=2)
            second.join(timeout=2)

        assert responses == ["https://stream/audio", "https://stream/audio"]
        request_get.assert_called_once()
