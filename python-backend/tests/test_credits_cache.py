from src.lib.music.credits import SongCreditsCache


class SongCreditsCacheTests:
    def test_cache_is_bounded_and_keeps_recently_used_entries(self) -> None:
        cache = SongCreditsCache(max_entries=2)
        cache.put("first", {"description": "first"})
        cache.put("second", {"description": "second"})

        assert cache.get("first") == {"description": "first"}
        cache.put("third", {"description": "third"})

        assert cache.get("second") is None
        assert cache.get("first") == {"description": "first"}
        assert cache.get("third") == {"description": "third"}
