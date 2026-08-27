import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from src.lib.music.lyrics import LyricsService
from src.lib.runtime.metadata_cache import MetadataCache


class _Response:
    def __init__(self, payload: object, *, text: str = "", ok: bool = True) -> None:
        self._payload = payload
        self.text = text
        self.ok = ok

    def json(self) -> object:
        return self._payload


class LyricsProviderTests(unittest.TestCase):
    def test_translation_uses_the_legacy_endpoint_when_the_primary_endpoint_fails(self) -> None:
        failed_response = Mock()
        failed_response.raise_for_status.side_effect = requests.ConnectionError("unavailable")
        fallback_response = Mock()
        fallback_response.json.return_value = [[["Hallo"]]]

        with patch(
            "src.lib.music.lyrics.requests.get", side_effect=[failed_response, fallback_response]
        ) as get:
            translated = LyricsService._google_translate_batch(["Hello"], "DE")

        self.assertEqual(translated, ["Hallo"])
        self.assertEqual(
            [call.args[0] for call in get.call_args_list],
            [
                "https://clients5.google.com/translate_a/single",
                "https://translate.googleapis.com/translate_a/single",
            ],
        )

    def test_paxsenix_picker_requires_matching_title_and_artist(self) -> None:
        songs = [
            {
                "id": 1,
                "name": "Bad Apple (from Lovelight)",
                "artists": [{"name": "Masayoshi Minoshima"}],
                "duration": 220_000,
            },
            {
                "id": 2,
                "name": "Bad Apple!!",
                "artists": [{"name": "nomico"}],
                "duration": 219_000,
            },
        ]

        selected = LyricsService._pick_paxsenix_song(
            songs, "Bad Apple!!", "nomico", 220_000
        )

        self.assertEqual(selected["id"], 2)

    def test_portato_extracts_unescaped_qrc(self) -> None:
        response = _Response(
            {
                "lyrics": (
                    '<Lyric_1 LyricContent="[0,1000]Hello(0,500)'
                    ' &amp; world(500,500)\\n" />'
                )
            }
        )

        with patch("src.lib.music.lyrics.requests.get", return_value=response):
            result = LyricsService._lookup_portato(
                "Song", "Artist", "Album", "180", "portato"
            )

        self.assertEqual(result["source"], "Better Lyrics Portato")
        self.assertIn("& world", result["qrc"])


class LyricsFastTierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        cache = MetadataCache(Path(self.tempdir.name) / "cache.sqlite3")
        self.service = LyricsService(
            cache_settings=SimpleNamespace(enabled={}),
            musixmatch=SimpleNamespace(),
            metadata_cache=cache,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_prefers_lrclib_even_when_a_lower_priority_provider_finishes_first(self) -> None:
        def slow_lrclib(title: str, artist: str, source: str) -> dict[str, object]:
            time.sleep(0.05)
            return {"source": "LRCLIB", "synced": "lrclib-lyrics", "plain": None}

        def fast_better(
            title: str, artist: str, album: str, duration: str, source: str
        ) -> dict[str, object]:
            return {"source": "Better Lyrics", "ttml": "better-lyrics"}

        with (
            patch.object(LyricsService, "_lookup_lrclib", staticmethod(slow_lrclib)),
            patch.object(LyricsService, "_lookup_better_lyrics", staticmethod(fast_better)),
            patch.object(LyricsService, "_lookup_portato", staticmethod(lambda *a, **k: None)),
        ):
            result = self.service._lookup_fast_tier("Song", "Artist", "Album", "180", "auto")

        self.assertEqual(result["source"], "LRCLIB")

    def test_falls_back_to_a_lower_priority_provider_when_higher_priority_misses(self) -> None:
        with (
            patch.object(LyricsService, "_lookup_lrclib", staticmethod(lambda *a, **k: None)),
            patch.object(LyricsService, "_lookup_better_lyrics", staticmethod(lambda *a, **k: None)),
            patch.object(
                LyricsService,
                "_lookup_portato",
                staticmethod(lambda *a, **k: {"source": "Better Lyrics Portato", "qrc": "x"}),
            ),
        ):
            result = self.service._lookup_fast_tier("Song", "Artist", "Album", "180", "auto")

        self.assertEqual(result["source"], "Better Lyrics Portato")

    def test_unison_versions_fetches_missing_bodies_and_dedupes_display_names(self) -> None:
        search_payload = {
            "success": True,
            "data": [
                {
                    "id": "c1",
                    "song": "Song",
                    "artist": "Artist",
                    "submitter": {"keyId": "u1"},
                    "voteCount": 5,
                },
                {
                    "id": "c2",
                    "song": "Song",
                    "artist": "Artist",
                    "submitter": {"keyId": "u1"},
                    "voteCount": 3,
                },
            ],
        }

        def fake_get(url: str, params: object = None, timeout: object = None) -> _Response:
            if url.endswith("/lyrics/c1"):
                return _Response(
                    {"data": {"lyrics": "lyrics-1", "format": "lrc", "submitter": {"keyId": "u1"}}}
                )
            if url.endswith("/lyrics/c2"):
                return _Response(
                    {"data": {"lyrics": "lyrics-2", "format": "lrc", "submitter": {"keyId": "u1"}}}
                )
            if url.endswith("/lyrics/search"):
                return _Response(search_payload)
            if "/leaderboard/users/" in url:
                return _Response({"data": {"displayName": "Name-u1"}})
            return _Response({}, ok=False)

        with patch("src.lib.music.lyrics.requests.get", side_effect=fake_get) as get:
            versions = self.service.unison_versions("", "Song", "Artist", "", "")

        self.assertEqual({v["id"] for v in versions}, {"c1", "c2"})
        self.assertEqual({v["lyrics"] for v in versions}, {"lyrics-1", "lyrics-2"})
        for version in versions:
            self.assertEqual(version["submitterName"], "Name-u1")

        # Both candidates share submitter "u1" — the display name lookup must be deduped.
        leaderboard_calls = [call for call in get.call_args_list if "/leaderboard/users/" in call.args[0]]
        self.assertEqual(len(leaderboard_calls), 1)
