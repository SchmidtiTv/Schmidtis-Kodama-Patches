from unittest.mock import patch

from route_test_support import RouteTestCase


class OperationsRouteTests(RouteTestCase):
    def test_ipv4_first_setting_can_be_read_and_changed(self) -> None:
        assert self.client.get("/network/ipv4-first").json == {"enabled": True}

        disabled = self.client.post("/network/ipv4-first", json={"enabled": False})
        assert disabled.status_code == 200
        assert disabled.json == {"enabled": False}
        assert not self.network_settings.ipv4_first_enabled

        enabled = self.client.post("/network/ipv4-first", json={"enabled": True})
        assert enabled.status_code == 200
        assert enabled.json == {"enabled": True}
        assert self.network_settings.ipv4_first_enabled

    def test_ipv4_first_setting_requires_a_boolean(self) -> None:
        response = self.client.post("/network/ipv4-first", json={"enabled": "false"})

        assert response.status_code == 400
        assert response.json == {"error": "enabled must be a boolean"}

    def test_debug_info_route_reports_runtime_context(self) -> None:
        with (
            patch("src.routes.operations.debug.info.time.time", return_value=1065.0),
            patch("src.routes.operations.debug.info.shutil.which", return_value="/usr/bin/node"),
        ):
            response = self.client.get("/debug/info")

        assert response.status_code == 200
        assert response.json["node"] == "/usr/bin/node"
        assert response.json["profile"] == "default"
        assert response.json["uptime"] == "1m 5s"
        assert response.json["authed"]
        assert response.json["cookieRefreshAgeS"] == 65
        assert response.json["lastStreamError"] is None
        assert "python" in response.json
        assert "logs" in response.json

    def test_local_fonts_route_returns_a_list(self) -> None:
        response = self.client.get("/api/local-fonts")
        assert response.status_code == 200
        assert isinstance(response.json, list)

    def test_overlay_routes(self) -> None:
        page = self.client.get("/overlay")
        assert page.status_code == 200
        assert b"Overlay" in page.data
        assert page.headers["X-Frame-Options"] == "ALLOWALL"

        stream = self.client.get("/overlay/stream")
        assert stream.status_code == 200
        assert b'"title": "Song"' in stream.data

        assert self.client.post("/overlay/push", json={"title": "Now Playing"}).json == {"ok": True}
        assert self.overlay_server.state["title"] == "Now Playing"

        assert self.client.get("/overlay/config").json["version"] == 2
        assert self.client.post("/overlay/config", json={"version": 2, "layers": ["x"]}).json == {
            "ok": True
        }
        assert self.overlay_server.config["layers"] == ["x"]

        assert self.client.post("/overlay/server/start", json={"port": 9900}).json == {
            "ok": True,
            "port": 9900,
        }
        assert self.overlay_server.started_ports == [9900]
        assert self.client.get("/overlay/status").json == {"running": True, "clients": 0}
        assert self.client.post("/overlay/server/stop").json == {"ok": True}
        assert self.client.get("/overlay/status").json == {"running": False, "clients": 0}

    def test_remote_desktop_routes_are_localhost_only(self) -> None:
        forbidden = self.client.post(
            "/remote/_enable",
            json={"enabled": True},
            environ_overrides={"REMOTE_ADDR": "192.0.2.10"},
        )
        assert forbidden.status_code == 403

        enabled = self.client.post(
            "/remote/_enable",
            json={"enabled": True, "token": "tok", "trusted": [{"id": "phone", "name": "Phone"}]},
        )
        assert enabled.json["enabled"] is True
        assert enabled.json["token"] == "tok"

        status = self.client.get("/remote/_status")
        assert status.json["devices"][0]["id"] == "phone"

        self.remote_control.devices["new"] = {"name": "New", "status": "pending"}
        assert self.client.post(
            "/remote/_device", json={"id": "new", "action": "approve"}
        ).json == {"ok": True}
        assert self.remote_control.devices["new"]["status"] == "approved"
        assert (
            self.client.post(
                "/remote/_device", json={"id": "missing", "action": "approve"}
            ).status_code
            == 404
        )

        assert self.client.post("/remote/_push", json={"title": "Song"}).json == {"ok": True}
        self.remote_control.commands.append({"action": "next"})
        assert self.client.get("/remote/_poll").json == {"commands": [{"action": "next"}]}
        self.remote_control.commands.append({"action": "prev"})
        assert self.client.post("/remote/_sync", json={"state": {"title": "Synced"}}).json == {
            "commands": [{"action": "prev"}]
        }
        assert self.remote_control.state["title"] == "Synced"

    def test_remote_phone_routes_and_page(self) -> None:
        self.client.post("/remote/_enable", json={"enabled": True, "token": "tok"})

        assert (
            self.client.post(
                "/remote/hello", json={"token": "bad", "deviceId": "phone"}
            ).status_code
            == 403
        )
        hello = self.client.post(
            "/remote/hello", json={"token": "tok", "deviceId": "phone", "name": "Phone"}
        )
        assert hello.json == {"status": "pending"}

        pending_state = self.client.get("/remote/state?token=tok&deviceId=phone")
        assert pending_state.json == {"status": "pending"}
        assert (
            self.client.post(
                "/remote/cmd", json={"token": "tok", "deviceId": "phone", "action": "next"}
            ).status_code
            == 403
        )

        self.remote_control.devices["phone"]["status"] = "approved"
        approved_state = self.client.get("/remote/state?token=tok&deviceId=phone")
        assert approved_state.json["status"] == "approved"
        assert "state" in approved_state.json

        assert self.client.post(
            "/remote/cmd", json={"token": "tok", "deviceId": "phone", "action": "next"}
        ).json == {"ok": True}
        assert self.client.post(
            "/remote/cmd",
            json={
                "token": "tok",
                "deviceId": "phone",
                "action": "seek",
                "position": 42.5,
            },
        ).json == {"ok": True}
        assert self.remote_control.commands[-1] == {"action": "seek", "position": 42.5}
        assert (
            self.client.post(
                "/remote/cmd", json={"token": "tok", "deviceId": "phone", "action": "bad"}
            ).status_code
            == 400
        )
        page = self.client.get("/remote")
        assert page.status_code == 200
        assert b"Remote" in page.data
