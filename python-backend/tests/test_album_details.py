import tempfile
import unittest
from pathlib import Path

from src.lib.integrations.musicbrainz import MusicBrainzError
from src.lib.music.album_details import AlbumDetailsError, AlbumDetailsFinder
from src.lib.runtime.metadata_cache import MetadataCache


class FakeMusicBrainz:
    def __init__(
        self,
        releases: list[dict[str, object]] | None = None,
        release: dict[str, object] | None = None,
        search_error: bool = False,
        get_error: bool = False,
    ) -> None:
        self.releases = releases if releases is not None else []
        self.release = release or {}
        self.search_error = search_error
        self.get_error = get_error
        self.requested_id: str | None = None

    def search_releases(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        if self.search_error:
            raise MusicBrainzError
        return self.releases

    def get_release(self, release_id: str, inc: str = "") -> dict[str, object]:
        if self.get_error:
            raise MusicBrainzError
        self.requested_id = release_id
        return self.release


class AlbumDetailsFinderTests(unittest.TestCase):
    def test_returns_none_when_no_release_matches(self) -> None:
        finder = AlbumDetailsFinder(musicbrainz=FakeMusicBrainz(releases=[]))

        self.assertIsNone(finder.find("Daft Punk", "Discovery"))

    def test_picks_the_highest_scoring_candidate_and_fetches_its_details(self) -> None:
        musicbrainz = FakeMusicBrainz(
            releases=[
                {"id": "low-score", "score": 40},
                {"id": "high-score", "score": 95},
            ],
            release={
                "id": "high-score",
                "title": "Discovery",
                "date": "2001-03-07",
                "artist-credit": [{"name": "Daft Punk"}],
                "label-info": [{"label": {"name": "Virgin"}, "catalog-number": "VIRCD200"}],
                "media": [
                    {
                        "tracks": [
                            {"title": "One More Time", "position": 1, "length": 320000},
                        ]
                    }
                ],
            },
        )
        finder = AlbumDetailsFinder(musicbrainz=musicbrainz)

        details = finder.find("Daft Punk", "Discovery")

        self.assertEqual(musicbrainz.requested_id, "high-score")
        self.assertEqual(
            details,
            {
                "id": "high-score",
                "title": "Discovery",
                "date": "2001-03-07",
                "artists": "Daft Punk",
                "labels": ["Virgin"],
                "catalogNumbers": ["VIRCD200"],
                "tracks": [{"title": "One More Time", "position": 1, "durationMs": 320000}],
                "coverArtUrl": "https://coverartarchive.org/release/high-score/front-500",
            },
        )

    def test_catalog_numbers_are_empty_when_label_info_omits_them(self) -> None:
        musicbrainz = FakeMusicBrainz(
            releases=[{"id": "release-id", "score": 100}],
            release={"id": "release-id", "label-info": [{"label": {"name": "Virgin"}}]},
        )
        finder = AlbumDetailsFinder(musicbrainz=musicbrainz)

        details = finder.find("Daft Punk", "Discovery")

        self.assertEqual(details["labels"], ["Virgin"])
        self.assertEqual(details["catalogNumbers"], [])

    def test_raises_album_details_error_when_search_fails(self) -> None:
        finder = AlbumDetailsFinder(musicbrainz=FakeMusicBrainz(search_error=True))

        with self.assertRaises(AlbumDetailsError):
            finder.find("Daft Punk", "Discovery")

    def test_raises_album_details_error_when_fetch_fails(self) -> None:
        musicbrainz = FakeMusicBrainz(releases=[{"id": "release-id", "score": 100}], get_error=True)
        finder = AlbumDetailsFinder(musicbrainz=musicbrainz)

        with self.assertRaises(AlbumDetailsError):
            finder.find("Daft Punk", "Discovery")

    def test_ignores_candidates_missing_a_usable_id(self) -> None:
        musicbrainz = FakeMusicBrainz(releases=[{"score": 100}])
        finder = AlbumDetailsFinder(musicbrainz=musicbrainz)

        self.assertIsNone(finder.find("Daft Punk", "Discovery"))

    def test_caches_a_found_result_and_skips_the_musicbrainz_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            cache = MetadataCache(Path(tempdir) / "cache.sqlite3")
            musicbrainz = FakeMusicBrainz(
                releases=[{"id": "release-id", "score": 100}],
                release={"id": "release-id", "title": "Discovery"},
            )
            finder = AlbumDetailsFinder(musicbrainz=musicbrainz, metadata_cache=cache)

            first = finder.find("Daft Punk", "Discovery")
            musicbrainz.search_error = True  # a second network call would now raise
            second = finder.find("Daft Punk", "Discovery")

            self.assertEqual(first, second)
            self.assertEqual(first["title"], "Discovery")

    def test_caches_a_not_found_result_and_skips_the_musicbrainz_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            cache = MetadataCache(Path(tempdir) / "cache.sqlite3")
            musicbrainz = FakeMusicBrainz(releases=[])
            finder = AlbumDetailsFinder(musicbrainz=musicbrainz, metadata_cache=cache)

            self.assertIsNone(finder.find("Unknown Artist", "Unknown Album"))
            musicbrainz.search_error = True  # a second network call would now raise
            self.assertIsNone(finder.find("Unknown Artist", "Unknown Album"))

    def test_cache_key_is_case_and_whitespace_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            cache = MetadataCache(Path(tempdir) / "cache.sqlite3")
            musicbrainz = FakeMusicBrainz(
                releases=[{"id": "release-id", "score": 100}],
                release={"id": "release-id", "title": "Discovery"},
            )
            finder = AlbumDetailsFinder(musicbrainz=musicbrainz, metadata_cache=cache)

            finder.find("Daft Punk", "Discovery")
            musicbrainz.search_error = True
            cached = finder.find("  daft punk  ", "  DISCOVERY  ")

            self.assertEqual(cached["title"], "Discovery")
