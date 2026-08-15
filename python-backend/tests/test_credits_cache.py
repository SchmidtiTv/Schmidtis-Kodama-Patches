from src.lib.music.credits import SongCreditsCache
from src.lib.providers import SongCredits


class SongCreditsCacheTests:
    def test_cache_is_bounded_and_keeps_recently_used_entries(self) -> None:
        cache = SongCreditsCache(max_entries=2)
        cache.put("first", SongCredits("first"))
        cache.put("second", SongCredits("second"))

        assert cache.get("first") == SongCredits("first")
        cache.put("third", SongCredits("third"))

        assert cache.get("second") is None
        assert cache.get("first") == SongCredits("first")
        assert cache.get("third") == SongCredits("third")
