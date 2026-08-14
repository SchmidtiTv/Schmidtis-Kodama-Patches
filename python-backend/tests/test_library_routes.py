import json
from typing import cast
from unittest.mock import patch

from route_test_support import JsonValue, RouteTestCase, TestResponse


class HistoryRouteTests(RouteTestCase):
    def test_history_sync_requires_authentication_and_records_the_song(self) -> None:
        missing = self.client.post("/ytmusic/history", json={})
        assert missing.status_code == 400

        recorded = self.client.post("/ytmusic/history", json={"videoId": "vid"})
        assert recorded.status_code == 200
        assert recorded.json == {"ok": True, "status": 204}
        assert len(self.music_session.client.history_items) == 1

        self.profile_repository.local_profiles.add("default")
        local = self.client.post("/ytmusic/history", json={"videoId": "vid"})
        assert local.status_code == 403


def sse_events(response: TestResponse) -> list[JsonValue]:
    events: list[JsonValue] = []
    for block in response.data.decode("utf-8").strip().split("\n\n"):
        if block.startswith("data: "):
            events.append(cast("JsonValue", json.loads(block[6:])))
    return events


class LibraryListingRouteTests(RouteTestCase):
    def test_online_library_listing_routes(self) -> None:
        playlists = self.client.get("/library/playlists")
        assert playlists.status_code == 200
        assert playlists.json["playlists"][0]["playlistId"] == "pl"

        albums = self.client.get("/library/albums")
        assert albums.status_code == 200
        assert albums.json["albums"][0]["artists"] == "Artist"

        artists = self.client.get("/library/artists")
        assert artists.status_code == 200
        assert artists.json["artists"][0]["artist"] == "Artist"
        assert self.music_session.client.library_playlists_limit is None
        assert self.music_session.client.library_albums_limit is None
        assert self.music_session.client.library_artists_limit is None

    def test_local_library_listing_routes(self) -> None:
        self.profile_repository.local_profiles.add("default")

        playlists = self.client.get("/library/playlists")
        assert playlists.status_code == 200
        assert playlists.json["playlists"][0]["playlistId"] == "local-pl"
        assert playlists.json["playlists"][0]["count"] == "1"

        assert self.client.get("/library/albums").json == {"albums": []}
        assert self.client.get("/library/artists").json == {"artists": []}

    def test_library_listing_omits_the_duplicate_liked_songs_playlist(self) -> None:
        self.music_session.client.get_library_playlists = lambda limit=None: [
            {"playlistId": "LM", "title": "Liked Songs", "thumbnails": []},
            {"playlistId": "pl", "title": "Playlist", "thumbnails": []},
        ]

        playlists = self.client.get("/library/playlists")

        assert [playlist["playlistId"] for playlist in playlists.json["playlists"]] == ["pl"]


class PlaylistRouteTests(RouteTestCase):
    def test_playlist_mix_is_profile_scoped_and_local_to_kodama(self) -> None:
        assert self.client.get("/playlist/pl/mix").json == {
            "playlistId": "pl",
            "version": 1,
            "enabled": False,
            "analysisVersion": None,
            "smartReorder": False,
            "trackOrder": [],
            "trackAnalysis": {},
            "transitions": [],
        }

        enabled = self.client.put("/playlist/pl/mix", json={"enabled": True})
        assert enabled.status_code == 200
        assert enabled.json["enabled"] is True

        self.music_session.state.current_profile = "second"
        assert self.client.get("/playlist/pl/mix").json["enabled"] is False

        self.music_session.state.current_profile = "default"
        assert self.client.delete("/playlist/pl/mix").json == {"ok": True}
        assert self.client.get("/playlist/pl/mix").json["enabled"] is False

    def test_playlist_mix_validates_its_local_config_boundary(self) -> None:
        assert self.client.put("/playlist/pl/mix", json={}).status_code == 400
        assert self.client.put("/playlist/pl/mix", json={"enabled": "yes"}).status_code == 400

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

        assert updated.status_code == 200
        assert updated.json["smartReorder"]
        assert updated.json["trackOrder"][1]["instanceId"] == "set-b"
        assert updated.json["transitions"][0]["preset"] == "blend"
        assert updated.json["transitions"][0]["beatOffsetMs"] == -12.0

        invalid = self.client.put(
            "/playlist/pl/mix",
            json={"transitions": [{"fromTrackInstanceId": "a", "toTrackInstanceId": "b"}]},
        )
        assert invalid.status_code == 400

    def test_playlist_mix_analysis_routes_preserve_validation_and_job_responses(self) -> None:
        assert self.client.post("/playlist/pl/mix/analysis").status_code == 400
        assert (
            self.client.post("/playlist/pl/mix/analysis", json={"tracks": ["bad"]}).status_code
            == 400
        )
        assert (
            self.client.post(
                "/playlist/pl/mix/analysis",
                json={"tracks": [{"instanceId": "", "videoId": "video-a"}]},
            ).status_code
            == 400
        )

        started = self.client.post(
            "/playlist/pl/mix/analysis",
            json={
                "tracks": [
                    {"instanceId": " set-a ", "videoId": " video-a "},
                    {"instanceId": "set-b", "videoId": "video-b"},
                ]
            },
        )

        assert started.status_code == 202
        assert started.json == {
            "jobId": "job-1",
            "playlistId": "pl",
            "status": "queued",
            "total": 2,
            "completed": 0,
            "tracks": {},
        }
        assert self.mix_analysis.started_with == (
            "default",
            "pl",
            [
                {"instanceId": "set-a", "videoId": "video-a"},
                {"instanceId": "set-b", "videoId": "video-b"},
            ],
        )
        assert self.client.get("/playlist/pl/mix/analysis/job-1").json == started.json
        assert self.client.get("/playlist/pl/mix/analysis/missing").status_code == 404

    def test_online_playlist_mutation_routes(self) -> None:
        assert self.client.post("/playlist/create", json={}).status_code == 400
        created = self.client.post(
            "/playlist/create",
            json={
                "title": "New",
                "description": "Desc",
                "privacyStatus": "PUBLIC",
                "videoIds": ["vid"],
            },
        )
        assert created.json == {"ok": True, "playlistId": "created-pl"}
        assert self.music_session.client.created_playlists == [("New", "Desc", "PUBLIC", ["vid"])]

        assert self.client.post("/playlist/pl/add", json={}).status_code == 400
        assert self.client.post("/playlist/pl/add", json={"videoIds": ["vid"]}).json == {"ok": True}
        assert self.music_session.client.added_playlist_items == [("pl", ["vid"])]
        assert self.playlist_cache.purged[-1] == ("pl", "default")

        assert self.client.post("/playlist/pl/remove", json={}).status_code == 400
        videos = [{"videoId": "vid", "setVideoId": "set"}]
        assert self.client.post("/playlist/pl/remove", json={"videos": videos}).json == {"ok": True}
        assert self.music_session.client.removed_playlist_items == [("pl", videos)]

        assert self.client.post("/playlist/pl/edit", json={"title": "Edited"}).json == {"ok": True}
        assert self.music_session.client.edited_playlists[-1][0] == "pl"

        assert self.client.delete("/playlist/pl").json == {"ok": True}
        assert self.music_session.client.deleted_playlists == ["pl"]

    def test_online_playlist_fetch_and_stream_cache(self) -> None:
        playlist = self.client.get("/playlist/pl")
        assert playlist.status_code == 200
        assert playlist.json["title"] == "Playlist"
        assert playlist.json["tracks"][0]["videoId"] == "vid"

        streamed = self.client.get("/playlist/pl/stream")
        events = sse_events(streamed)
        assert events[0]["type"] == "loading"
        assert events[1]["type"] == "header"
        assert events[-1] == {"type": "done"}
        assert self.playlist_cache.saved[-1][0:2] == ("pl", "default")

        cached = self.client.get("/playlist/pl/stream")
        cached_events = sse_events(cached)
        assert cached_events[0]["cached"]
        assert cached_events[-1] == {"type": "done"}

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

        def watch_playlist(**_kwargs: object) -> dict[str, object]:
            return {
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

        with patch.object(
            self.music_session.system_client,
            "get_watch_playlist",
            side_effect=watch_playlist,
        ):
            events = sse_events(self.client.get("/playlist/video-pl/stream?refresh=1"))
        track_events = [event for event in events if event["type"] == "tracks"]

        assert [len(event["tracks"]) for event in track_events] == [4, 1]
        assert [track["videoId"] for event in track_events for track in event["tracks"]] == [
            f"audio-{index}" for index in range(5)
        ]
        assert events.index(track_events[0]) < len(events) - 1
        assert events[-1] == {"type": "done"}

    def test_in_memory_playlist_cache_is_profile_scoped(self) -> None:
        default_events = sse_events(self.client.get("/playlist/LM/stream"))
        assert default_events[1]["title"] == "Liked Songs"
        assert ("default", "LM") in self.playlist_cache.playlist_cache

        self.music_session.state.current_profile = "second"
        second_events = sse_events(self.client.get("/playlist/LM/stream"))
        assert second_events[0]["type"] == "loading"
        assert not second_events[0].get("cached", False)
        assert ("second", "LM") in self.playlist_cache.playlist_cache

    def test_liked_songs_playlist_fetch_and_stream(self) -> None:
        playlist = self.client.get("/playlist/LM")
        assert playlist.status_code == 200
        assert playlist.json["title"] == "Liked Songs"
        assert playlist.json["tracks"][0]["videoId"] == "vid"

        events = sse_events(self.client.get("/playlist/LM/stream?refresh=1"))
        assert events[0]["type"] == "loading"
        assert events[1]["type"] == "header"
        assert events[-1] == {"type": "done"}

    def test_local_playlist_routes(self) -> None:
        self.profile_repository.local_profiles.add("default")

        created = self.client.post("/playlist/create", json={"title": "Local New"})
        assert created.status_code == 200
        assert created.json["ok"]

        assert self.client.post("/playlist/local-pl/add", json={"videoIds": ["vid"]}).json == {
            "ok": True
        }
        assert self.client.post(
            "/playlist/local-pl/remove", json={"videos": [{"videoId": "vid"}]}
        ).json == {"ok": True}
        assert self.client.post("/playlist/local-pl/edit", json={"title": "Edited"}).json == {
            "ok": True
        }

        playlist = self.client.get("/playlist/local-pl")
        assert playlist.status_code == 200
        assert playlist.json["title"] == "Local Playlist"
        assert playlist.json["tracks"][0]["videoId"] == "local-song"

        events = sse_events(self.client.get("/playlist/local-pl/stream"))
        assert events[0]["type"] == "header"
        assert events[0]["cached"]
        assert events[-1] == {"type": "done"}

        assert self.client.delete("/playlist/local-pl").json == {"ok": True}


class LibraryDetailRouteTests(RouteTestCase):
    def test_song_seeded_radio_uses_video_id_and_radio_mode(self) -> None:
        radio = self.client.get("/radio/_?videoId=vNIgpTYiGe0")

        assert radio.status_code == 200
        assert radio.json["tracks"][0]["videoId"] == "vid"
        assert self.music_session.client.watch_playlist_calls[-1] == {
            "videoId": "vNIgpTYiGe0",
            "playlistId": None,
            "limit": 50,
            "radio": True,
        }

    def test_radio_album_artist_and_song_meta_routes(self) -> None:
        radio = self.client.get("/radio/pl")
        assert radio.status_code == 200
        assert radio.json["tracks"][0]["videoId"] == "vid"

        album = self.client.get("/album/alb")
        assert album.status_code == 200
        assert album.json["title"] == "Album"
        assert album.json["tracks"][0]["album"] == "Album"
        assert self.album_cache.saved[-1][0] == "alb"

        cached = self.client.get("/album/alb")
        assert cached.json["title"] == "Album"

        artist = self.client.get("/artist/UCartist")
        assert artist.status_code == 200
        assert artist.json["name"] == "Artist"
        assert artist.json["songsBrowseId"] == "songs"

        self.band_member_finder.find = lambda artist_name: [{"name": "Member"}]
        members = self.client.get("/artist/UCartist/members?name=Artist")
        assert members.json == {"members": [{"name": "Member"}]}

        assert self.client.post(
            "/artist/UCartist/subscribe", json={"channelId": "UCchannel"}
        ).json == {"ok": True}
        assert self.music_session.client.subscribed_artists == [["UCchannel"]]
        assert self.client.post(
            "/artist/UCartist/unsubscribe", json={"channelId": "UCchannel"}
        ).json == {"ok": True}
        assert self.music_session.client.unsubscribed_artists == [["UCchannel"]]

        meta = self.client.get("/song/meta/vid")
        assert meta.status_code == 200
        assert meta.json["duration"] == "3:05"

        info = self.client.get("/song/info/vid")
        assert info.status_code == 200
        assert info.json == {"artistBrowseId": "UCartist", "albumBrowseId": "MPREb"}

    def test_song_stats_route_formats_raw_counts(self) -> None:
        class StatsResponse:
            status_code = 200

            def json(self) -> object:
                return {"viewCount": 1_250_000, "likes": 42_500, "dislikes": 321}

        with patch(
            "src.routes.library.song.stats.by_video_id.index.requests.get",
            return_value=StatsResponse(),
        ) as request:
            stats = self.client.get("/song/stats/vid")

        assert stats.status_code == 200
        assert stats.json["views"] == "1.2M"
        assert stats.json["likes"] == "42.5K"
        assert stats.json["dislikes"] == "321"
        assert stats.json["viewsRaw"] == 1_250_000
        request.assert_called_once()

    def test_song_stats_route_reports_unavailable_stats(self) -> None:
        class FailedStatsResponse:
            status_code = 404

        with patch(
            "src.routes.library.song.stats.by_video_id.index.requests.get",
            return_value=FailedStatsResponse(),
        ):
            response = self.client.get("/song/stats/vid")

        assert response.status_code == 502
        assert response.json == {"error": "stats unavailable"}

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

        with patch(
            "src.routes.library.song.credits.by_video_id.index.requests.post",
            return_value=JsonResponse(),
        ) as post:
            first = self.client.get("/song/credits/vid")
            second = self.client.get("/song/credits/vid")

        assert first.json == {"description": "Credits text"}
        assert second.json == {"description": "Credits text"}
        assert post.call_count == 1
