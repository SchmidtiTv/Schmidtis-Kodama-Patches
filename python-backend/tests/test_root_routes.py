from route_test_support import RouteTestCase


class RootMusicRouteTests(RouteTestCase):
    def test_root_music_routes(self) -> None:
        assert self.client.get("/status").json["ok"] is True
        assert self.client.get("/search").json == {"results": []}
        assert self.client.get("/search?q=song").json["results"][0]["type"] == "song"
        assert (
            self.client.get("/search?q=artist&filter=artists").json["results"][0]["type"]
            == "artist"
        )
        assert (
            self.client.get("/search?q=album&filter=albums").json["results"][0]["type"] == "album"
        )
        all_results = self.client.get("/search?q=anything&filter=all").json["results"]
        assert {result["type"] for result in all_results} == {"song", "artist", "album", "playlist"}
        assert (
            next(result for result in all_results if result["type"] == "artist")["title"]
            == "Artist"
        )
        assert (
            next(result for result in all_results if result["type"] == "artist")["browseId"]
            == "UCartist"
        )
        assert (
            next(result for result in all_results if result["type"] == "playlist")["playlistId"]
            == "PLtest"
        )
        top_artist = next(result for result in all_results if result.get("browseId") == "UCtop")
        assert top_artist["title"] == "Top Artist"
        shelf_song = next(result for result in all_results if result.get("videoId") == "shelf")
        assert shelf_song["artists"] == ""
        assert shelf_song["artistLinks"] == []
        assert self.client.get("/search/suggestions?q=song").json == {
            "suggestions": ["Song", "Artist", "Album", "Playlist", "Shelf Song"]
        }
        assert self.client.get("/search/suggestions?q=x").json == {"suggestions": []}
        assert self.client.get("/home").json["sections"][0]["items"][0]["videoId"] == "vid"
        assert (
            self.client.get("/artist_albums?channelId=UCartist&params=abc").json["albums"][0][
                "title"
            ]
            == "Album"
        )
        assert self.client.get("/artist_albums").status_code == 400

        liked = self.client.get("/liked")
        assert liked.status_code == 200
        assert liked.json["tracks"][0]["videoId"] == "vid"
        assert liked.json["total"] == 1
        assert not liked.json["hasMore"]
        assert self.music_session.client.liked_songs_limits == [50]
        assert self.client.get("/liked?offset=50&limit=50").json["offset"] == 50
        assert self.music_session.client.liked_songs_limits == [50, 100]
        assert self.client.get("/liked/ids").json == {"ids": ["vid"]}
        assert self.music_session.client.liked_songs_limits == [50, 100, None]
        like = self.client.post("/like/vid", json={"rating": "LIKE"})
        assert like.json == {"ok": True, "rating": "LIKE"}
        assert self.music_session.client.ratings == [("vid", "LIKE")]

        self.profile_repository.local_profiles.add("default")
        local_like = self.client.post(
            "/like/local",
            json={
                "rating": "LIKE",
                "title": "Local",
                "artists": "Artist",
                "album": "Album",
                "thumbnail": "",
                "duration": "1:00",
            },
        )
        assert local_like.json == {"ok": True, "rating": "LIKE"}
        assert self.client.get("/liked/ids").json == {"ids": ["local"]}
        assert self.client.get("/liked").json["tracks"][0]["title"] == "Local"
