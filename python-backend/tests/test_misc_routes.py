from unittest.mock import patch

from route_test_support import RouteTestCase


class MiscRouteTests(RouteTestCase):
    def test_imgproxy_news_feedback_clientlog_and_shutdown(self) -> None:
        proxied = self.client.get("/imgproxy?url=https://example.test/image.jpg")
        assert proxied.status_code == 200
        assert proxied.headers["X-Cache"] == "MISS"
        assert proxied.data == b"img"

        project_root = self.root / "python-backend"
        news_path = project_root.parent / "updates" / "news.json"
        news_path.parent.mkdir(parents=True)
        news_path.write_text('[{"id": "release-1"}]', encoding="utf-8")
        with patch("src.routes.news.PROJECT_ROOT", project_root):
            news = self.client.get("/news")
        assert news.status_code == 200
        assert news.json == [{"id": "release-1"}]
        assert self.client.post("/feedback", json={"title": "Bug"}).status_code == 503

        self.feedback_service.configured = True
        feedback = self.client.post(
            "/feedback", json={"title": "Bug", "description": "Details", "includeLogs": False}
        )
        assert feedback.json == {"ok": True}
        assert len(self.feedback_service.submissions) == 1

        assert self.client.open("/clientlog", method="OPTIONS").status_code == 204
        with patch("builtins.print"):
            assert self.client.post("/clientlog", data="hello").status_code == 204

        with patch("src.routes.root.shutdown.threading.Thread") as thread:
            thread.return_value.start.return_value = None
            shutdown = self.client.post("/shutdown")
        assert shutdown.data == b"ok"
