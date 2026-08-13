from unittest.mock import patch

from route_test_support import RouteTestCase


class LastFMRouteTests(RouteTestCase):
    def test_lastfm_session_persists_for_active_local_profile(self) -> None:
        self.music_session.state.current_profile = "local_user"
        self.profile_repository.metadata["local_user"] = {
            "displayName": "Local User",
            "type": "local",
        }

        session = self.client.post("/lastfm/session", json={"token": "tok"})

        assert session.json == {"connected": True, "username": "bob"}
        assert self.profile_repository.metadata["local_user"]["lastfm_session"] == "new-sk"
        assert self.profile_repository.metadata["default"]["lastfm_session"] == "sk"

    def test_lastfm_routes(self) -> None:
        assert self.client.get("/lastfm/status").json["username"] == "alice"
        connect = self.client.get("/lastfm/connect")
        assert connect.status_code == 200
        assert connect.json["token"] == "tok"

        session = self.client.post("/lastfm/session", json={"token": "tok"})
        assert session.json == {"connected": True, "username": "bob"}
        assert self.profile_repository.metadata["default"]["lastfm_session"] == "new-sk"

        with patch("src.routes.lastFm.session.lastfm_client") as lastfm_client:
            lastfm_client.return_value.lastfm_call.return_value = (
                True,
                {"session": {"key": "", "name": "bob"}},
            )
            invalid_session = self.client.post("/lastfm/session", json={"token": "tok"})
        assert invalid_session.status_code == 502
        assert invalid_session.json == {"error": "invalid_session"}
        assert self.profile_repository.metadata["default"]["lastfm_session"] == "new-sk"

        for path in ("/lastfm/now-playing", "/lastfm/scrobble", "/lastfm/love", "/lastfm/unlove"):
            response = self.client.post(
                path, json={"artist": "Artist", "track": "Song", "duration": "180"}
            )
            assert response.json == {"ok": True}

        assert self.client.post("/lastfm/disconnect").json == {"connected": False}
        assert "lastfm_session" not in self.profile_repository.metadata["default"]
        missing_meta = self.client.post("/lastfm/love", json={"artist": "Artist", "track": "Song"})
        assert missing_meta.status_code == 400
