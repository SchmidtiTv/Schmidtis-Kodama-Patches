import base64
import json
import unittest

from src.lib.music.canvas_artwork import CanvasArtworkFinder, CanvasQuery, query_from_payload


class FakeResponse:
    def __init__(self, payload: object, text: str = "") -> None:
        self.payload = payload
        self.text = text

    def json(self) -> object:
        return self.payload

    def raise_for_status(self) -> None:
        return None


class CanvasArtworkFinderTests(unittest.TestCase):
    def test_vivimusic_match_is_preferred_and_cached(self) -> None:
        calls = []

        def get(url: str, **_kwargs: object) -> FakeResponse:
            calls.append(url)
            return FakeResponse(
                {
                    "items": [
                        {
                            "song": "Song (Radio Edit)",
                            "artist": "The Artist",
                            "album": "Album",
                            "url": "https://example.test/canvas.mp4",
                        }
                    ]
                }
            )

        finder = CanvasArtworkFinder(get=get)
        query = CanvasQuery("Song", "The Artist", "Album", 185, "vivimusic")

        self.assertEqual(finder.find(query).source, "vivimusic")  # type: ignore[union-attr]
        self.assertEqual(finder.find(query).url, "https://example.test/canvas.mp4")  # type: ignore[union-attr]
        self.assertEqual(len(calls), 1)

    def test_tidal_video_cover_becomes_cdn_url(self) -> None:
        def get(url: str, **_kwargs: object) -> FakeResponse:
            if "vivimusicanvas" in url:
                return FakeResponse([])
            return FakeResponse(
                {
                    "tracks": {
                        "items": [
                            {
                                "title": "Song",
                                "artists": [{"name": "Artist"}],
                                "album": {"videoCover": "a-b-c-d-e"},
                            }
                        ]
                    }
                }
            )

        artwork = CanvasArtworkFinder(get=get).find(
            CanvasQuery("Song", "Artist", "Album", None, "tidal")
        )

        self.assertEqual(artwork.source, "tidal")  # type: ignore[union-attr]
        self.assertEqual(artwork.url, "https://resources.tidal.com/videos/a/b/c/d/e/1280x1280.mp4")  # type: ignore[union-attr]

    def test_apple_token_from_bundle_is_accepted_only_for_amp_web_play(self) -> None:
        payload = (
            base64.urlsafe_b64encode(
                json.dumps({"iss": "AMPWebPlay", "exp": 2_000_000_000}).encode()
            )
            .decode()
            .rstrip("=")
        )
        token = f"eyJhbGciOiJub25lIn0.{payload}.signature"

        def get(url: str, **_kwargs: object) -> FakeResponse:
            if url.endswith("/browse"):
                return FakeResponse({}, '<script src="/assets/index-main.js"></script>')
            if url.endswith("index-main.js"):
                return FakeResponse({}, token)
            if "vivimusicanvas" in url:
                return FakeResponse([])
            if "api.tidal" in url:
                return FakeResponse({})
            return FakeResponse(
                {
                    "results": {
                        "albums": {
                            "data": [
                                {
                                    "type": "albums",
                                    "id": "album-id",
                                    "attributes": {
                                        "name": "Song",
                                        "artistName": "Artist",
                                        "editorialVideo": {
                                            "video": "https://example.test/apple.m3u8"
                                        },
                                    },
                                }
                            ]
                        }
                    }
                }
            )

        artwork = CanvasArtworkFinder(get=get, now=lambda: 1_700_000_000).find(
            CanvasQuery("Song", "Artist", "Album", None, "apple_music")
        )

        self.assertEqual(artwork.source, "apple_music")  # type: ignore[union-attr]
        self.assertEqual(artwork.url, "https://example.test/apple.m3u8")  # type: ignore[union-attr]


class CanvasQueryTests(unittest.TestCase):
    def test_payload_requires_title_and_artist_and_bounds_duration(self) -> None:
        self.assertIsNone(query_from_payload({"title": "Song"}))
        self.assertEqual(
            query_from_payload({"title": " Song ", "artist": " Artist ", "durationSeconds": 185}),
            CanvasQuery("Song", "Artist", "", 185, "auto"),
        )
        self.assertEqual(
            query_from_payload({"title": "Song", "artist": "Artist", "durationSeconds": 0}),
            CanvasQuery("Song", "Artist", "", None, "auto"),
        )
        self.assertEqual(
            query_from_payload({"title": "Song", "artist": "Artist", "source": "tidal"}),
            CanvasQuery("Song", "Artist", "", None, "tidal"),
        )
