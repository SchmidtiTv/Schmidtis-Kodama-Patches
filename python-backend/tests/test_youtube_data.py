import unittest

from src.lib.music.youtube_data import YoutubeResponseMapper


class YoutubeResponseMapperTests(unittest.TestCase):
    def test_select_thumbnail_uses_largest_fallback_when_no_image_meets_minimum_size(self) -> None:
        thumbnail = YoutubeResponseMapper.select_thumbnail(
            [
                {"width": 60, "url": "https://example.test/60.jpg"},
                {"width": 120, "url": "https://example.test/120.jpg"},
            ]
        )

        self.assertEqual(thumbnail, "https://example.test/120.jpg")
