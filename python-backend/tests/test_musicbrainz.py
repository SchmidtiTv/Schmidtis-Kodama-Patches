import unittest

import requests

from src.lib.integrations.musicbrainz import MUSICBRAINZ_URL, MusicBrainz, MusicBrainzError


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class MusicBrainzTests(unittest.TestCase):
    def test_search_artists_returns_matches(self) -> None:
        def get(url: str, **_kwargs: object) -> FakeResponse:
            self.assertEqual(url, f"{MUSICBRAINZ_URL}/artist/")
            return FakeResponse({"artists": [{"id": "group-id", "name": "The Group"}]})

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        self.assertEqual(
            client.search_artists("artist:The Group AND type:group"),
            [{"id": "group-id", "name": "The Group"}],
        )

    def test_search_artists_returns_empty_list_when_field_is_missing_or_malformed(self) -> None:
        def get(_url: str, **_kwargs: object) -> FakeResponse:
            return FakeResponse({"artists": "not-a-list"})

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        self.assertEqual(client.search_artists("artist:Solo"), [])

    def test_search_releases_returns_matches(self) -> None:
        def get(url: str, **_kwargs: object) -> FakeResponse:
            self.assertEqual(url, f"{MUSICBRAINZ_URL}/release/")
            return FakeResponse({"releases": [{"id": "release-id", "title": "Discovery"}]})

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        self.assertEqual(
            client.search_releases('release:"Discovery" AND artist:"Daft Punk"'),
            [{"id": "release-id", "title": "Discovery"}],
        )

    def test_search_releases_returns_empty_list_when_field_is_missing_or_malformed(self) -> None:
        def get(_url: str, **_kwargs: object) -> FakeResponse:
            return FakeResponse({"releases": "not-a-list"})

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        self.assertEqual(client.search_releases('release:"Discovery"'), [])

    def test_get_artist_fetches_by_id_with_inc_relations(self) -> None:
        requested: dict[str, object] = {}

        def get(url: str, params: dict[str, object], **_kwargs: object) -> FakeResponse:
            requested["url"] = url
            requested["params"] = params
            return FakeResponse({"relations": []})

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        self.assertEqual(client.get_artist("group-id", "artist-rels"), {"relations": []})
        self.assertEqual(requested["url"], f"{MUSICBRAINZ_URL}/artist/group-id")
        self.assertEqual(requested["params"], {"inc": "artist-rels", "fmt": "json"})

    def test_get_release_fetches_by_id_with_default_inc(self) -> None:
        requested: dict[str, object] = {}

        def get(url: str, params: dict[str, object], **_kwargs: object) -> FakeResponse:
            requested["url"] = url
            requested["params"] = params
            return FakeResponse({"id": "release-id", "media": []})

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        self.assertEqual(client.get_release("release-id"), {"id": "release-id", "media": []})
        self.assertEqual(requested["url"], f"{MUSICBRAINZ_URL}/release/release-id")
        self.assertEqual(
            requested["params"], {"inc": "recordings+artist-credits+labels", "fmt": "json"}
        )

    def test_get_release_accepts_a_custom_inc(self) -> None:
        requested: dict[str, object] = {}

        def get(url: str, params: dict[str, object], **_kwargs: object) -> FakeResponse:
            requested["params"] = params
            return FakeResponse({"id": "release-id"})

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        client.get_release("release-id", inc="labels")

        self.assertEqual(requested["params"], {"inc": "labels", "fmt": "json"})

    def test_raises_musicbrainz_error_on_request_failure(self) -> None:
        def get(_url: str, **_kwargs: object) -> FakeResponse:
            raise requests.ConnectionError("boom")

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        with self.assertRaises(MusicBrainzError):
            client.search_artists("artist:The Group")

    def test_raises_musicbrainz_error_on_non_dict_payload(self) -> None:
        class ListResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> list[object]:
                return []

        def get(_url: str, **_kwargs: object) -> ListResponse:
            return ListResponse()

        client = MusicBrainz(get=get, monotonic=lambda: 1, sleep=lambda _seconds: None)

        with self.assertRaises(MusicBrainzError):
            client.get_artist("group-id", "artist-rels")

    def test_serializes_requests_to_stay_within_the_rate_limit(self) -> None:
        clock = 1000.0

        def monotonic() -> float:
            return clock

        waited: list[float] = []

        def sleep(seconds: float) -> None:
            nonlocal clock
            waited.append(seconds)
            clock += seconds

        def get(_url: str, **_kwargs: object) -> FakeResponse:
            return FakeResponse({"relations": []})

        client = MusicBrainz(get=get, monotonic=monotonic, sleep=sleep)

        client.get_artist("first", "artist-rels")
        client.get_artist("second", "artist-rels")

        self.assertEqual(waited, [1.0])
