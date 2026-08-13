from route_test_support import RouteTestCase


class DiscoveryRouteTests(RouteTestCase):
    def test_podcast_route_normalizes_metadata_and_playable_episodes(self) -> None:
        response = self.client.get("/podcast/podcast-pl")
        assert response.status_code == 200
        assert response.json["title"] == "Podcast"
        assert response.json["author"] == {"name": "Host", "id": "UChost"}
        assert response.json["episodes"][0]["videoId"] == "episode"
        assert len(response.json["episodes"]) == 1

    def test_mood_categories_deduplicate_params_by_section(self) -> None:
        response = self.client.get("/mood/categories")
        assert response.status_code == 200
        assert response.json["For you"] == [{"title": "Energize", "params": "energy"}]
        assert response.json["Genres"] == [{"title": "Jazz", "params": "jazz"}]

    def test_mood_playlists_requires_params_and_parses_browse_response(self) -> None:
        assert self.client.get("/mood/playlists").status_code == 400

        response = self.client.get("/mood/playlists?params=energy")
        assert response.status_code == 200
        assert response.json[0]["type"] == "playlist"
        assert response.json[0]["playlistId"] == "mood-pl"
        assert response.json[1]["type"] == "song"
        assert response.json[1]["videoId"] == "mood-song"
        assert len(response.json) == 2
