import os
import tempfile
from pathlib import Path
from threading import Barrier, Lock, get_ident

from src.lib.music.band_members import REQUEST_TIMEOUT, BandMemberFinder


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class BandMemberFinderTests:
    def setup_method(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temporary_directory.name)

    def teardown_method(self) -> None:
        self.temporary_directory.cleanup()

    def test_finds_members_combines_roles_and_loads_portraits(self) -> None:
        group_id = "group-id"
        member_id = "member-id"
        responses: dict[str, dict[str, object]] = {
            "https://musicbrainz.org/ws/2/artist/": {
                "artists": [{"id": group_id, "name": "The Group"}],
            },
            f"https://musicbrainz.org/ws/2/artist/{group_id}": {
                "relations": [
                    {
                        "type": "member of band",
                        "target-type": "artist",
                        "artist": {"id": member_id, "name": "A Member"},
                        "attributes": ["vocals"],
                        "begin": "2001",
                    },
                    {
                        "type": "member of band",
                        "target-type": "artist",
                        "artist": {"id": member_id, "name": "A Member"},
                        "attributes": ["guitar", "vocals"],
                        "begin": "2005",
                        "ended": True,
                        "end": "2008",
                    },
                ],
            },
            f"https://musicbrainz.org/ws/2/artist/{member_id}": {
                "relations": [
                    {"type": "wikidata", "url": {"resource": "https://www.wikidata.org/wiki/Q123"}}
                ],
            },
            "https://www.wikidata.org/wiki/Special:EntityData/Q123.json": {
                "entities": {
                    "Q123": {
                        "claims": {"P18": [{"mainsnak": {"datavalue": {"value": "Member.jpg"}}}]},
                        "sitelinks": {"enwiki": {"url": "https://en.wikipedia.org/wiki/A_Member"}},
                    }
                },
            },
            "https://commons.wikimedia.org/w/api.php": {
                "query": {
                    "pages": {
                        "1": {"imageinfo": [{"thumburl": "https://commons.example/member.jpg"}]}
                    }
                },
            },
        }

        def get(url: str, **_kwargs: object) -> FakeResponse:
            return FakeResponse(responses[url])

        finder = BandMemberFinder(
            get=get,
            monotonic=lambda: 1,
            sleep=lambda _seconds: None,
            cache_dir=self.cache_dir,
        )

        assert finder.find("The Group") == [
            {
                "id": member_id,
                "name": "A Member",
                "roles": ["vocals"],
                "membershipDates": ["2001 \N{EN DASH} present"],
                "image": "https://commons.example/member.jpg",
                "wikipediaUrl": "https://en.wikipedia.org/wiki/A_Member",
            }
        ]

    def test_returns_no_members_when_no_group_matches(self) -> None:
        requests = []

        def get(url: str, **_kwargs: object) -> FakeResponse:
            requests.append(url)
            return FakeResponse({"artists": []})

        finder = BandMemberFinder(
            get=get,
            monotonic=lambda: 1,
            sleep=lambda _seconds: None,
            cache_dir=self.cache_dir,
        )

        assert finder.find("Solo Artist") == []
        assert finder.find(" solo artist ") == []
        assert requests == ["https://musicbrainz.org/ws/2/artist/"]

    def test_loads_member_details_concurrently_with_short_timeouts(self) -> None:
        group_id = "group-id"
        member_ids = ["member-one", "member-two"]
        wikidata_barrier = Barrier(len(member_ids))
        request_threads: set[int] = set()
        request_timeouts: list[object] = []
        calls_lock = Lock()

        def get(url: str, **kwargs: object) -> FakeResponse:
            with calls_lock:
                request_timeouts.append(kwargs.get("timeout"))
            if url.endswith("/artist/"):
                return FakeResponse({"artists": [{"id": group_id}]})
            if url.endswith(f"/artist/{group_id}"):
                return FakeResponse(
                    {
                        "relations": [
                            {
                                "type": "member of band",
                                "target-type": "artist",
                                "artist": {"id": member_id, "name": member_id},
                            }
                            for member_id in member_ids
                        ]
                    }
                )
            if any(url.endswith(f"/artist/{member_id}") for member_id in member_ids):
                member_number = member_ids.index(url.rsplit("/", 1)[-1]) + 1
                return FakeResponse(
                    {
                        "relations": [
                            {
                                "type": "wikidata",
                                "url": {
                                    "resource": f"https://www.wikidata.org/wiki/Q{member_number}"
                                },
                            }
                        ]
                    }
                )
            if "Special:EntityData" in url:
                with calls_lock:
                    request_threads.add(get_ident())
                wikidata_barrier.wait(timeout=1)
                wikidata_id = url.rsplit("/", 1)[-1].removesuffix(".json")
                return FakeResponse({"entities": {wikidata_id: {"claims": {}, "sitelinks": {}}}})
            raise AssertionError(f"Unexpected URL: {url}")

        finder = BandMemberFinder(
            get=get,
            monotonic=lambda: 1,
            sleep=lambda _seconds: None,
            cache_dir=self.cache_dir,
        )

        members = finder.find("The Group")

        assert [member["name"] for member in members] == member_ids
        assert len(request_threads) == len(member_ids)
        assert request_timeouts
        assert set(request_timeouts) == {REQUEST_TIMEOUT}

    def test_reuses_cached_members_after_restart(self) -> None:
        def get(url: str, **_kwargs: object) -> FakeResponse:
            if url.endswith("/artist/"):
                return FakeResponse({"artists": [{"id": "group-id"}]})
            if url.endswith("/artist/group-id"):
                return FakeResponse({"relations": []})
            raise AssertionError(f"Unexpected URL: {url}")

        first_finder = BandMemberFinder(
            get=get,
            monotonic=lambda: 1,
            sleep=lambda _seconds: None,
            cache_dir=self.cache_dir,
        )
        assert first_finder.find("The Group") == []

        def fail_get(_url: str, **_kwargs: object) -> FakeResponse:
            raise AssertionError("Persistent cache should avoid network requests")

        restarted_finder = BandMemberFinder(
            get=fail_get,
            monotonic=lambda: 1,
            sleep=lambda _seconds: None,
            cache_dir=self.cache_dir,
        )
        assert restarted_finder.find(" the group ") == []

    def test_ignores_expired_disk_cache(self) -> None:
        calls: list[str] = []

        def get(url: str, **_kwargs: object) -> FakeResponse:
            calls.append(url)
            return FakeResponse({"artists": []})

        finder = BandMemberFinder(
            get=get,
            monotonic=lambda: 1,
            wall_time=lambda: 100,
            sleep=lambda _seconds: None,
            cache_ttl=10,
            cache_dir=self.cache_dir,
        )
        assert finder.find("The Group") == []
        cache_path = next(self.cache_dir.glob("*.json"))
        os.utime(cache_path, (50, 50))

        restarted_finder = BandMemberFinder(
            get=get,
            monotonic=lambda: 1,
            wall_time=lambda: 100,
            sleep=lambda _seconds: None,
            cache_ttl=10,
            cache_dir=self.cache_dir,
        )
        assert restarted_finder.find("The Group") == []
        assert len(calls) == 2
