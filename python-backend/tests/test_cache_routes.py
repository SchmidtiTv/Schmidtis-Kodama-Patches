from unittest.mock import patch

from route_test_support import RouteTestCase


class CacheRouteTests(RouteTestCase):
    def test_cache_routes_use_isolated_directories(self) -> None:
        with patch("src.routes.cache.stats.config_dirs", self.cache_dirs):
            stats = self.client.get("/cache/stats")
        assert stats.status_code == 200
        assert "playlists" in stats.json
        assert stats.json["songs"]["enabled"]

        assert self.client.get("/cache/settings").json["images"] is True
        assert self.client.post("/cache/settings", json={"images": False}).json == {"ok": True}
        assert not self.cache_settings.enabled["images"]

        self.playlist_cache.put("x", "default", {"tracks": []})
        with patch("src.routes.cache.clear.config_dirs", self.cache_dirs):
            cleared = self.client.post("/cache/clear", json={"category": "playlists"})
        assert cleared.json == {"ok": True}
        assert self.playlist_cache.playlist_cache == {}
        assert list(self.cache_dirs.PLAYLIST_CACHE_DIR.iterdir()) == []

        self.download_service.status["cleared-song"] = "done"
        with patch("src.routes.cache.clear.config_dirs", self.cache_dirs):
            cleared = self.client.post("/cache/clear", json={"category": "songs"})
        assert cleared.json == {"ok": True}
        assert self.download_service.status == {}
        assert self.client.get("/song/download/status/cleared-song").json == {"status": "not_found"}
