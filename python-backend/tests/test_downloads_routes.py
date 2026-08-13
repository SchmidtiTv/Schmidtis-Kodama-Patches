from unittest.mock import patch

from route_test_support import RouteTestCase


class DownloadRouteTests(RouteTestCase):
    def test_download_routes_start_report_and_queue_downloads(self) -> None:
        started = self.client.post(
            "/song/download/vid",
            json={
                "title": "Song",
                "artists": "Artist",
                "album": "Album",
                "duration": "3:00",
                "thumbnail": "thumb",
            },
        )
        assert started.json == {"ok": True, "status": "downloading"}
        assert self.download_service.started[0][0] == "vid"
        assert self.download_service.started[0][1]["title"] == "Song"

        again = self.client.post("/song/download/vid", json={"title": "Song"})
        assert again.json == {"ok": True, "status": "downloading"}
        assert len(self.download_service.started) == 1

        assert self.client.get("/song/download/status/vid").json == {"status": "downloading"}
        queue = self.client.get("/downloads/queue")
        assert queue.json["queue"][0]["videoId"] == "vid"

    def test_download_route_returns_done_for_already_cached_song(self) -> None:
        self.download_service.add_cached("cached")
        response = self.client.post("/song/download/cached", json={"title": "Cached"})
        assert response.json == {"ok": True, "status": "done"}
        assert self.download_service.status["cached"] == "done"
        assert self.client.get("/song/download/status/cached").json == {"status": "done"}


class CachedSongRouteTests(RouteTestCase):
    def test_cached_song_routes_serve_list_and_delete(self) -> None:
        cached_path = self.download_service.add_cached("cached", suffix=".mp3", content=b"mp3 data")

        served = self.client.get("/song/cached/cached")
        assert served.status_code == 200
        assert served.content_type == "audio/mpeg"
        assert served.data == b"mp3 data"
        served.close()
        assert cached_path.exists()

        assert self.client.get("/song/cached/missing").status_code == 404
        assert self.client.get("/song/cached/list").json == {
            "songs": [{"videoId": "cached", "title": "Cached Song"}]
        }

        assert self.client.delete("/song/cached/cached").json == {"ok": True}
        assert self.download_service.deleted == ["cached"]

        batch = self.client.post("/songs/cached/delete-batch", json={"videoIds": ["a", "b"]})
        assert batch.json == {"ok": True, "removed": 2}
        assert self.download_service.deleted[-2:] == ["a", "b"]


class ExportRouteTests(RouteTestCase):
    def test_export_routes_validate_start_and_report_status(self) -> None:
        assert self.client.post("/song/export/vid", json={}).status_code == 400

        with patch("builtins.print"):
            response = self.client.post(
                "/song/export/vid",
                json={
                    "output_path": "/tmp/song.opus",
                    "format": "opus",
                    "title": "Song",
                    "artists": "Artist",
                    "album": "Album",
                    "albumBrowseId": "alb",
                    "thumbnail": "thumb",
                },
            )
        assert response.json == {"ok": True, "status": "exporting"}
        assert self.export_service.started[0][0:3] == ("vid", "/tmp/song.opus", "opus")
        assert self.export_service.started[0][3]["year"] == "2026"

        repeat = self.client.post("/song/export/vid", json={"output_path": "/tmp/song.opus"})
        assert repeat.json == {"ok": True, "status": "exporting"}
        assert len(self.export_service.started) == 1

        assert self.client.get("/song/export/status/vid").json == {"status": "exporting"}
        assert self.client.get("/song/export/status/missing").json == {"status": "not_found"}
        assert self.client.get("/song/export/ffmpeg-available").json == {"available": True}

    def test_export_uses_song_upload_year_when_album_year_is_missing(self) -> None:
        with (
            patch.object(self.music_session.client, "get_album", return_value={}),
            patch("builtins.print"),
        ):
            response = self.client.post(
                "/song/export/song-year",
                json={
                    "output_path": "/tmp/song.mp3",
                    "format": "mp3",
                    "albumBrowseId": "missing-year",
                },
            )
        assert response.status_code == 200
        assert self.export_service.started[0][3]["year"] == "2024"


class ToolUpdateRouteTests(RouteTestCase):
    def test_ffmpeg_routes(self) -> None:
        assert self.client.get("/ffmpeg/status").json == {"available": True}
        assert self.client.get("/ffmpeg/check-update").json == self.ffmpeg.update_payload

        stream = self.client.get("/ffmpeg/download?force=1")
        assert stream.status_code == 200
        assert b'"status": "done"' in stream.data
        assert self.ffmpeg.download_forces == [True]

    def test_ytdlp_routes(self) -> None:
        assert self.client.get("/ytdlp/check-update").json == self.ytdlp.check_payload
        assert self.client.post("/ytdlp/update").json == self.ytdlp.update_payload

        self.ytdlp.update_payload = {"ok": False, "error": "boom"}
        self.ytdlp.update_status = 502
        failed = self.client.post("/ytdlp/update")
        assert failed.status_code == 502
        assert failed.json == {"ok": False, "error": "boom"}
