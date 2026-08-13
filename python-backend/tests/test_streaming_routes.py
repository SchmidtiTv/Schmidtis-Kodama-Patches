from route_test_support import RouteTestCase


class StreamingRouteTests(RouteTestCase):
    def test_streaming_routes(self) -> None:
        assert self.client.get("/stream/vid").json == {"url": "https://stream/vid"}
        assert self.client.get("/stream-prepare/vid").json == {"path": "/tmp/vid.m4a"}
        assert self.client.get("/audio-stream/vid", headers={"Range": "bytes=0-1"}).data == b"audio"
        assert self.client.get("/audio-stream/error").status_code == 502
        assert self.client.get("/audio-stream/vid/warm").json == {"ok": True}

        offset = self.client.get("/video-sync/offset/vid")
        assert offset.status_code == 200
        assert offset.json["counterpartVideoId"] == "official-vid"

        video = self.client.get("/video-sync/stream/official-vid?maxHeight=720")
        assert video.status_code == 200
        assert video.json == {"url": "https://video/official-vid", "maxHeight": 720}
