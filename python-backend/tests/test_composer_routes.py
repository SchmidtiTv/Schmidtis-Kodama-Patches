from route_test_support import RouteTestCase


class ComposerRouteTests(RouteTestCase):
    def test_composer_routes(self) -> None:
        health = self.client.get("/composer-bridge/health")
        assert health.json["status"] == "ok"
        assert health.headers["Access-Control-Allow-Origin"] == "https://composer.boidu.dev"

        app_response = self.client.get("/composer-app/")
        assert b"Composer" in app_response.data
        app_response.close()
        assert self.client.get("/composer-bridge/autocache").json == {"enabled": True}
        assert self.client.post("/composer-bridge/autocache", json={"enabled": False}).json == {
            "enabled": False
        }

        thumb = self.client.get("/composer-bridge/thumb/vid")
        assert thumb.status_code == 200
        assert thumb.content_type == "image/png"
        assert self.client.get("/composer-bridge/thumb/missing").status_code == 404

        cached = self.client.get("/composer-bridge/audio/cached")
        assert cached.status_code == 200
        assert cached.content_type == "audio/mp4"
        cached.close()
        streamed = self.client.get("/composer-bridge/audio/live")
        assert streamed.status_code == 200
        assert streamed.data == b"upstream"
