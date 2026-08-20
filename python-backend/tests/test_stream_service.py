import threading
import unittest
from unittest.mock import MagicMock, call, patch

from src.config import config_ytdlp
from src.lib.music.stream import StreamService


class StreamServiceTests(unittest.TestCase):
    def setUp(self) -> None:
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

        self.assertEqual((payload, status), ({"url": "https://stream/audio"}, 200))
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

        self.assertEqual((payload, status), ({"url": "https://stream/working"}, 200))
        cookie_stream = extract.call_args_list[1].kwargs["extra_opts"]["cookiefile"]
        self.assertEqual(cookie_stream.getvalue(), "cookies")
        self.assertEqual(
            probe.call_args_list,
            [
                call("video", "https://stream/rejected"),
                call("video", "https://stream/working"),
            ],
        )

    def test_stream_resolution_serializes_the_same_video_id(self) -> None:
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
                self.assertTrue(release_first.wait(timeout=2))
            else:
                second_started.set()
            return {"url": f"https://stream/{video_id}"}

        with (
            patch.object(self.service, "_extract_url", side_effect=extract),
            patch.object(self.service, "_probe_audio_url", return_value=True),
        ):
            first = threading.Thread(
                target=lambda: responses.append(self.service.resolve_stream("same"))
            )
            second = threading.Thread(
                target=lambda: responses.append(self.service.resolve_stream("same"))
            )
            first.start()
            self.assertTrue(first_started.wait(timeout=2))
            second.start()
            # Duplicate requests for the SAME video must not run yt-dlp concurrently.
            self.assertFalse(second_started.wait(timeout=0.1))
            release_first.set()
            first.join(timeout=2)
            second.join(timeout=2)

        self.assertTrue(second_started.is_set())
        self.assertEqual(
            responses,
            [
                ({"url": "https://stream/same"}, 200),
                ({"url": "https://stream/same"}, 200),
            ],
        )

    def test_stream_resolution_does_not_serialize_across_different_video_ids(self) -> None:
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
                self.assertTrue(release_first.wait(timeout=2))
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
            self.assertTrue(first_started.wait(timeout=2))
            second.start()
            # A different video_id must resolve immediately, not wait behind "first".
            self.assertTrue(second_started.wait(timeout=2))
            release_first.set()
            first.join(timeout=2)
            second.join(timeout=2)

        self.assertEqual(
            sorted(responses, key=lambda response: str(response[0]["url"])),
            [
                ({"url": "https://stream/first"}, 200),
                ({"url": "https://stream/second"}, 200),
            ],
        )

    def test_resolve_audio_url_prunes_expired_cache_entries(self) -> None:
        self.service._audio_url_cache["stale"] = ("https://stream/stale", 0.0)  # already expired

        with (
            patch.object(self.service, "_extract_url", return_value={"url": "https://stream/x"}),
            patch.object(self.service, "_probe_audio_url", return_value=True),
        ):
            self.service.resolve_audio_url("fresh")

        self.assertNotIn("stale", self.service._audio_url_cache)
        self.assertIn("fresh", self.service._audio_url_cache)

    def test_concurrent_audio_resolution_runs_one_stream_request(self) -> None:
        started = threading.Event()
        release = threading.Event()
        responses = []
        call_count = 0
        count_lock = threading.Lock()

        def extract(video_id: str, *_args: object, **_kwargs: object) -> dict[str, str]:
            nonlocal call_count
            with count_lock:
                call_count += 1
            started.set()
            self.assertTrue(release.wait(timeout=2))
            return {"url": f"https://stream/{video_id}"}

        with (
            patch.object(self.service, "_extract_url", side_effect=extract),
            patch.object(self.service, "_probe_audio_url", return_value=True),
        ):
            first = threading.Thread(
                target=lambda: responses.append(self.service.resolve_audio_url("video"))
            )
            second = threading.Thread(
                target=lambda: responses.append(self.service.resolve_audio_url("video"))
            )
            first.start()
            self.assertTrue(started.wait(timeout=2))
            second.start()
            release.set()
            first.join(timeout=2)
            second.join(timeout=2)

        self.assertEqual(responses, ["https://stream/video", "https://stream/video"])
        # The in-flight de-dup means only the resolver thread actually calls yt-dlp — this now
        # runs fully in-process (no loopback HTTP request to the local /stream endpoint).
        self.assertEqual(call_count, 1)
