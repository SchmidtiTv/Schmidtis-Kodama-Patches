import json
from typing import cast
from unittest.mock import patch

from route_test_support import JsonValue, RouteTestCase, TestResponse
from src.lib import AlbumDetailsError
from src.lib.music.canvas_artwork import CanvasArtwork


class HistoryRouteTests(RouteTestCase):
    def test_history_sync_requires_authentication_and_records_the_song(self) -> None:
        missing = self.client.post("/ytmusic/history", json={})
        self.assertEqual(missing.status_code, 400)

        recorded = self.client.post("/ytmusic/history", json={"videoId": "vid"})
        self.assertEqual(recorded.status_code, 200)
        self.assertEqual(recorded.json, {"ok": True, "status": 204})
        self.assertEqual(len(self.music_session.client.history_items), 1)

        self.profile_repository.local_profiles.add("default")
        local = self.client.post("/ytmusic/history", json={"videoId": "vid"})
        self.assertEqual(local.status_code, 403)


def sse_events(response: TestResponse) -> list[JsonValue]:
    events: list[JsonValue] = []
    for block in response.data.decode("utf-8").strip().split("\n\n"):
        if block.startswith("data: "):
            events.append(cast(JsonValue, json.loads(block[6:])))
    return events


class LibraryListingRouteTests(RouteTestCase):
    def test_song_canvas_validates_and_returns_optional_artwork(self) -> None:
        invalid = self.client.post("/song/canvas", json={"title": "Song"})
        self.assertEqual(invalid.status_code, 400)

        unavailable = self.client.post(
            "/song/canvas", json={"title": "Song", "artist": "Artist", "album": "Album"}
        )
        self.assertEqual(unavailable.status_code, 200)
        self.assertEqual(unavailable.json, {"url": None})

        self.canvas_artwork_finder.result = CanvasArtwork(
            "tidal", "https://example.test/canvas.mp4"
        )
        resolved = self.client.post(
            "/song/canvas",
            json={
                "title": "Song",
                "artist": "Artist",
                "album": "Album",
                "durationSeconds": 185,
                "source": "tidal",
            },
        )
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(
            resolved.json,
            {"source": "tidal", "url": "https://example.test/canvas.mp4"},
        )
        self.assertEqual(self.canvas_artwork_finder.queries[-1].duration_seconds, 185)
        self.assertEqual(self.canvas_artwork_finder.queries[-1].source, "tidal")

    def test_online_library_listing_routes(self) -> None:
        playlists = self.client.get("/library/playlists")
        self.assertEqual(playlists.status_code, 200)
        self.assertEqual(playlists.json["playlists"][0]["playlistId"], "pl")

        albums = self.client.get("/library/albums")
        self.assertEqual(albums.status_code, 200)
        self.assertEqual(albums.json["albums"][0]["artists"], "Artist")

        artists = self.client.get("/library/artists")
        self.assertEqual(artists.status_code, 200)
        self.assertEqual(artists.json["artists"][0]["artist"], "Artist")
        self.assertIsNone(self.music_session.client.library_playlists_limit)
        self.assertIsNone(self.music_session.client.library_albums_limit)
        self.assertIsNone(self.music_session.client.library_artists_limit)

    def test_local_library_listing_routes(self) -> None:
        self.profile_repository.local_profiles.add("default")

        playlists = self.client.get("/library/playlists")
        self.assertEqual(playlists.status_code, 200)
        self.assertEqual(playlists.json["playlists"][0]["playlistId"], "local-pl")
        self.assertEqual(playlists.json["playlists"][0]["count"], "1")

        self.assertEqual(self.client.get("/library/albums").json, {"albums": []})
        self.assertEqual(self.client.get("/library/artists").json, {"artists": []})

    def test_library_listing_omits_the_duplicate_liked_songs_playlist(self) -> None:
        self.music_session.client.get_library_playlists = lambda limit=None: [
            {"playlistId": "LM", "title": "Liked Songs", "thumbnails": []},
            {"playlistId": "pl", "title": "Playlist", "thumbnails": []},
        ]

        playlists = self.client.get("/library/playlists")

        self.assertEqual(
            [playlist["playlistId"] for playlist in playlists.json["playlists"]], ["pl"]
        )


class PlaylistRouteTests(RouteTestCase):
    def test_playlist_mix_is_profile_scoped_and_local_to_kodama(self) -> None:
        self.assertEqual(
            self.client.get("/playlist/pl/mix").json,
            {
                "playlistId": "pl",
                "version": 1,
                "enabled": False,
                "analysisVersion": None,
                "smartReorder": False,
                "trackOrder": [],
                "trackAnalysis": {},
                "transitions": [],
            },
        )

        enabled = self.client.put("/playlist/pl/mix", json={"enabled": True})
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(enabled.json["enabled"], True)

        self.music_session.state.current_profile = "second"
        self.assertEqual(self.client.get("/playlist/pl/mix").json["enabled"], False)

        self.music_session.state.current_profile = "default"
        self.assertEqual(self.client.delete("/playlist/pl/mix").json, {"ok": True})
        self.assertEqual(self.client.get("/playlist/pl/mix").json["enabled"], False)

    def test_playlist_mix_validates_its_local_config_boundary(self) -> None:
        self.assertEqual(self.client.put("/playlist/pl/mix", json={}).status_code, 400)
        self.assertEqual(
            self.client.put("/playlist/pl/mix", json={"enabled": "yes"}).status_code, 400
        )

    def test_playlist_mix_persists_playlist_track_instances_and_transitions(self) -> None:
        updated = self.client.put(
            "/playlist/pl/mix",
            json={
                "smartReorder": True,
                "trackOrder": [
                    {"instanceId": "set-a", "videoId": "video-a"},
                    {"instanceId": "set-b", "videoId": "video-b"},
                ],
                "transitions": [
                    {
                        "fromTrackInstanceId": "set-a",
                        "toTrackInstanceId": "set-b",
                        "preset": "blend",
                        "bars": 4,
                        "volumeCurve": "smooth",
                        "eqCurve": "centerBass",
                        "effect": "lowPass",
                        "beatOffsetMs": -12,
                    }
                ],
            },
        )

        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.json["smartReorder"])
        self.assertEqual(updated.json["trackOrder"][1]["instanceId"], "set-b")
        self.assertEqual(updated.json["transitions"][0]["preset"], "blend")
        self.assertEqual(updated.json["transitions"][0]["beatOffsetMs"], -12.0)

        invalid = self.client.put(
            "/playlist/pl/mix",
            json={"transitions": [{"fromTrackInstanceId": "a", "toTrackInstanceId": "b"}]},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_online_playlist_mutation_routes(self) -> None:
        self.assertEqual(self.client.post("/playlist/create", json={}).status_code, 400)
        created = self.client.post(
            "/playlist/create",
            json={
                "title": "New",
                "description": "Desc",
                "privacyStatus": "PUBLIC",
                "videoIds": ["vid"],
            },
        )
        self.assertEqual(created.json, {"ok": True, "playlistId": "created-pl"})
        self.assertEqual(
            self.music_session.client.created_playlists, [("New", "Desc", "PUBLIC", ["vid"])]
        )

        self.assertEqual(self.client.post("/playlist/pl/add", json={}).status_code, 400)
        self.assertEqual(
            self.client.post("/playlist/pl/add", json={"videoIds": ["vid"]}).json, {"ok": True}
        )
        self.assertEqual(self.music_session.client.added_playlist_items, [("pl", ["vid"])])
        self.assertEqual(self.playlist_cache.purged[-1], ("pl", "default"))

        self.assertEqual(self.client.post("/playlist/pl/remove", json={}).status_code, 400)
        videos = [{"videoId": "vid", "setVideoId": "set"}]
        self.assertEqual(
            self.client.post("/playlist/pl/remove", json={"videos": videos}).json, {"ok": True}
        )
        self.assertEqual(self.music_session.client.removed_playlist_items, [("pl", videos)])

        self.assertEqual(
            self.client.post("/playlist/pl/edit", json={"title": "Edited"}).json, {"ok": True}
        )
        self.assertEqual(self.music_session.client.edited_playlists[-1][0], "pl")

        self.assertEqual(self.client.delete("/playlist/pl").json, {"ok": True})
        self.assertEqual(self.music_session.client.deleted_playlists, ["pl"])

    def test_online_playlist_fetch_and_stream_cache(self) -> None:
        playlist = self.client.get("/playlist/pl")
        self.assertEqual(playlist.status_code, 200)
        self.assertEqual(playlist.json["title"], "Playlist")
        self.assertEqual(playlist.json["tracks"][0]["videoId"], "vid")

        streamed = self.client.get("/playlist/pl/stream")
        events = sse_events(streamed)
        self.assertEqual(events[0]["type"], "loading")
        self.assertEqual(events[1]["type"], "header")
        self.assertEqual(events[-1], {"type": "done"})
        self.assertEqual(self.playlist_cache.saved[-1][0:2], ("pl", "default"))

        cached = self.client.get("/playlist/pl/stream")
        cached_events = sse_events(cached)
        self.assertTrue(cached_events[0]["cached"])
        self.assertEqual(cached_events[-1], {"type": "done"})

    def test_video_heavy_playlist_streams_resolved_tracks_incrementally(self) -> None:
        tracks = [
            {
                "videoId": f"video-{index}",
                "title": f"Video {index} (Official Video)",
                "artists": [{"name": "Artist", "id": "UCartist"}],
                "duration": "3:00",
                "videoType": "MUSIC_VIDEO_TYPE_OMV",
                "thumbnails": [],
            }
            for index in range(5)
        ]
        self.music_session.client.get_playlist = lambda playlist_id, limit=None: {
            "title": "Video Playlist",
            "thumbnails": [],
            "tracks": tracks,
        }
        self.music_session.system_client.get_watch_playlist = lambda **kwargs: {
            "tracks": [
                {
                    **track,
                    "videoId": f"audio-{index}",
                    "title": f"Video {index}",
                    "videoType": "MUSIC_VIDEO_TYPE_ATV",
                }
                for index, track in enumerate(tracks)
            ]
        }

        events = sse_events(self.client.get("/playlist/video-pl/stream?refresh=1"))
        track_events = [event for event in events if event["type"] == "tracks"]

        self.assertEqual([len(event["tracks"]) for event in track_events], [4, 1])
        self.assertEqual(
            [track["videoId"] for event in track_events for track in event["tracks"]],
            [f"audio-{index}" for index in range(5)],
        )
        self.assertLess(events.index(track_events[0]), len(events) - 1)
        self.assertEqual(events[-1], {"type": "done"})

    def test_in_memory_playlist_cache_is_profile_scoped(self) -> None:
        default_events = sse_events(self.client.get("/playlist/LM/stream"))
        self.assertEqual(default_events[1]["title"], "Liked Songs")
        self.assertIn(("default", "LM"), self.playlist_cache.playlist_cache)

        self.music_session.state.current_profile = "second"
        second_events = sse_events(self.client.get("/playlist/LM/stream"))
        self.assertEqual(second_events[0]["type"], "loading")
        self.assertFalse(second_events[0].get("cached", False))
        self.assertIn(("second", "LM"), self.playlist_cache.playlist_cache)

    def test_liked_songs_playlist_fetch_and_stream(self) -> None:
        playlist = self.client.get("/playlist/LM")
        self.assertEqual(playlist.status_code, 200)
        self.assertEqual(playlist.json["title"], "Liked Songs")
        self.assertEqual(playlist.json["tracks"][0]["videoId"], "vid")

        events = sse_events(self.client.get("/playlist/LM/stream?refresh=1"))
        self.assertEqual(events[0]["type"], "loading")
        self.assertEqual(events[1]["type"], "header")
        self.assertEqual(events[-1], {"type": "done"})

    def test_local_playlist_routes(self) -> None:
        self.profile_repository.local_profiles.add("default")

        created = self.client.post("/playlist/create", json={"title": "Local New"})
        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json["ok"])

        self.assertEqual(
            self.client.post("/playlist/local-pl/add", json={"videoIds": ["vid"]}).json,
            {"ok": True},
        )
        self.assertEqual(
            self.client.post(
                "/playlist/local-pl/remove", json={"videos": [{"videoId": "vid"}]}
            ).json,
            {"ok": True},
        )
        self.assertEqual(
            self.client.post("/playlist/local-pl/edit", json={"title": "Edited"}).json, {"ok": True}
        )

        playlist = self.client.get("/playlist/local-pl")
        self.assertEqual(playlist.status_code, 200)
        self.assertEqual(playlist.json["title"], "Local Playlist")
        self.assertEqual(playlist.json["tracks"][0]["videoId"], "local-song")

        events = sse_events(self.client.get("/playlist/local-pl/stream"))
        self.assertEqual(events[0]["type"], "header")
        self.assertTrue(events[0]["cached"])
        self.assertEqual(events[0]["description"], "Local description")
        self.assertEqual(events[-1], {"type": "done"})

        self.assertEqual(self.client.delete("/playlist/local-pl").json, {"ok": True})


class LibraryDetailRouteTests(RouteTestCase):
    def test_song_seeded_radio_uses_video_id_and_radio_mode(self) -> None:
        radio = self.client.get("/radio/_?videoId=vNIgpTYiGe0")

        self.assertEqual(radio.status_code, 200)
        self.assertEqual(radio.json["tracks"][0]["videoId"], "vid")
        self.assertEqual(
            self.music_session.client.watch_playlist_calls[-1],
            {"videoId": "vNIgpTYiGe0", "playlistId": None, "limit": 50, "radio": True},
        )

    def test_radio_album_artist_and_song_meta_routes(self) -> None:
        radio = self.client.get("/radio/pl")
        self.assertEqual(radio.status_code, 200)
        self.assertEqual(radio.json["tracks"][0]["videoId"], "vid")

        album = self.client.get("/album/alb")
        self.assertEqual(album.status_code, 200)
        self.assertEqual(album.json["title"], "Album")
        self.assertEqual(album.json["tracks"][0]["album"], "Album")
        self.assertEqual(self.album_cache.saved[-1][0], "alb")

        cached = self.client.get("/album/alb")
        self.assertEqual(cached.json["title"], "Album")

        artist = self.client.get("/artist/UCartist")
        self.assertEqual(artist.status_code, 200)
        self.assertEqual(artist.json["name"], "Artist")
        self.assertEqual(artist.json["songsBrowseId"], "songs")

        self.band_member_finder.find = lambda artist_name: [{"name": "Member"}]
        members = self.client.get("/artist/UCartist/members?name=Artist")
        self.assertEqual(members.json, {"members": [{"name": "Member"}]})

        missing_query = self.client.get("/album/alb/musicbrainz")
        self.assertEqual(missing_query.status_code, 400)

        self.album_details_finder.find = lambda artist, album: None
        no_match = self.client.get("/album/alb/musicbrainz?artist=Artist&album=Album")
        self.assertEqual(no_match.status_code, 404)

        self.album_details_finder.find = lambda artist, album: {"title": album, "artists": artist}
        matched = self.client.get("/album/alb/musicbrainz?artist=Artist&album=Album")
        self.assertEqual(matched.json, {"title": "Album", "artists": "Artist"})

        def raise_unavailable(artist: str, album: str) -> None:
            raise AlbumDetailsError

        self.album_details_finder.find = raise_unavailable
        unavailable = self.client.get("/album/alb/musicbrainz?artist=Artist&album=Album")
        self.assertEqual(unavailable.status_code, 502)

        self.assertEqual(
            self.client.post("/artist/UCartist/subscribe", json={"channelId": "UCchannel"}).json,
            {"ok": True},
        )
        self.assertEqual(self.music_session.client.subscribed_artists, [["UCchannel"]])
        self.assertEqual(
            self.client.post("/artist/UCartist/unsubscribe", json={"channelId": "UCchannel"}).json,
            {"ok": True},
        )
        self.assertEqual(self.music_session.client.unsubscribed_artists, [["UCchannel"]])

        meta = self.client.get("/song/meta/vid")
        self.assertEqual(meta.status_code, 200)
        self.assertEqual(meta.json["duration"], "3:05")

        info = self.client.get("/song/info/vid")
        self.assertEqual(info.status_code, 200)
        self.assertEqual(info.json, {"artistBrowseId": "UCartist", "albumBrowseId": "MPREb"})

    def test_song_stats_route_formats_raw_counts(self) -> None:
        class StatsResponse:
            status_code = 200

            def json(self) -> object:
                return {"viewCount": 1_250_000, "likes": 42_500, "dislikes": 321}

        with patch("src.routes.library.song.requests.get", return_value=StatsResponse()) as request:
            stats = self.client.get("/song/stats/vid")

        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json["views"], "1.2M")
        self.assertEqual(stats.json["likes"], "42.5K")
        self.assertEqual(stats.json["dislikes"], "321")
        self.assertEqual(stats.json["viewsRaw"], 1_250_000)
        request.assert_called_once()

    def test_song_stats_route_reports_unavailable_stats(self) -> None:
        class FailedStatsResponse:
            status_code = 404

        with patch("src.routes.library.song.requests.get", return_value=FailedStatsResponse()):
            response = self.client.get("/song/stats/vid")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json, {"error": "stats unavailable"})

    def test_song_credits_routes_use_cache_after_first_fetch(self) -> None:
        self.song_credits_cache.clear()
        payload = {
            "contents": {
                "twoColumnWatchNextResults": {
                    "results": {
                        "results": {
                            "contents": [
                                {
                                    "videoSecondaryInfoRenderer": {
                                        "attributedDescription": {"content": "Credits text"}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }

        class JsonResponse:
            def json(self) -> object:
                return payload

        with patch("src.routes.library.song.requests.post", return_value=JsonResponse()) as post:
            first = self.client.get("/song/credits/vid")
            second = self.client.get("/song/credits/vid")

        self.assertEqual(first.json, {"description": "Credits text"})
        self.assertEqual(second.json, {"description": "Credits text"})
        self.assertEqual(post.call_count, 1)
