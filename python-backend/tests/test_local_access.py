import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from typing import override
from unittest.mock import patch

from route_test_support import FakeUpstream, RouteTestCase

from src.lib.music.lyrics import LyricsService
from src.lib.profiles.meta import Meta
from src.lib.profiles.profile import Profile
from src.lib.runtime.logging import redact_secrets
from src.lib.security.file_names import UnsafeFileNameError, require_safe_file_stem
from src.lib.security.local_access import install_local_access_guard

LAN = {"REMOTE_ADDR": "192.168.1.50"}


class LocalAccessGuardTests(RouteTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        install_local_access_guard(self.app)

    def test_other_machines_reach_only_the_phone_remote_routes(self) -> None:
        for path in ("/debug/info", "/profiles", "/imgproxy?url=https://i.ytimg.com/a.jpg"):
            self.assertEqual(self.client.get(path, environ_base=LAN).status_code, 403, path)
        self.assertEqual(self.client.post("/shutdown", environ_base=LAN).status_code, 403)

        self.remote_control.token = "tok"
        missing_token = self.client.get("/remote/state?deviceId=phone", environ_base=LAN)
        self.assertEqual(missing_token.json, {"error": "invalid_token"})
        allowed = self.client.get(
            "/remote/state?deviceId=phone", headers={"X-Remote-Token": "tok"}, environ_base=LAN
        )
        self.assertEqual(allowed.status_code, 200)

    def test_loopback_requests_are_unaffected(self) -> None:
        self.assertEqual(self.client.get("/profiles").status_code, 200)
        self.assertEqual(
            self.client.get("/profiles", environ_base={"REMOTE_ADDR": "::1"}).status_code, 200
        )

    def test_rebound_host_names_are_refused(self) -> None:
        self.assertEqual(
            self.client.get("/profiles", headers={"Host": "attacker.example:9847"}).status_code, 403
        )
        self.assertEqual(
            self.client.get("/profiles", headers={"Host": "127.0.0.1:9847"}).status_code, 200
        )
        self.assertEqual(
            self.client.get("/profiles", headers={"Host": "[::1]:9847"}).status_code, 200
        )

    def test_cross_site_writes_are_refused(self) -> None:
        evil = self.client.post(
            "/profiles/delete", json={"name": "x"}, headers={"Origin": "https://evil.example"}
        )
        self.assertEqual(evil.status_code, 403)
        app = self.client.post(
            "/profiles/delete", json={"name": "x"}, headers={"Origin": "tauri://localhost"}
        )
        self.assertEqual(app.status_code, 200)
        phone = self.client.post(
            "/remote/hello",
            json={"token": "tok", "deviceId": "phone"},
            headers={"Origin": "http://192.168.1.10:9847", "Host": "192.168.1.10:9847"},
            environ_base=LAN,
        )
        self.assertNotIn("reason", phone.json)

    def test_shutdown_is_post_only(self) -> None:
        self.assertEqual(self.client.get("/shutdown").status_code, 405)


class ImageProxySafetyTests(RouteTestCase):
    def _proxy(
        self,
        body: bytes,
        content_type: str = "image/png",
        url: str = "https://i.ytimg.com/vi/x/a.jpg",
    ):
        upstream = FakeUpstream(status_code=200, content=body, content_type=content_type)
        with (
            patch("src.routes.root.imgproxy.config_dirs", self.cache_dirs),
            patch("src.routes.root.imgproxy.requests.get", return_value=upstream),
        ):
            return self.client.get(f"/imgproxy?url={url}")

    def test_documents_are_never_served_from_the_backend_origin(self) -> None:
        for body in (b"<script>x</script>", b"<svg onload=alert(1)>", b""):
            for claimed in ("text/html", "image/svg+xml", "image/png"):
                self.assertEqual(self._proxy(body, claimed).status_code, 415, (body, claimed))

    def test_images_are_typed_by_their_signature_with_nosniff_and_a_sandbox(self) -> None:
        response = self._proxy(b"\xff\xd8\xff\xe0jpeg", "application/octet-stream")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "image/jpeg")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", response.headers["Content-Security-Policy"])
        self.assertEqual(
            self._proxy(b"RIFF\0\0\0\0WEBPVP8 ", url="https://i.ytimg.com/b.webp").content_type,
            "image/webp",
        )

    def test_only_web_urls_are_fetched(self) -> None:
        self.assertEqual(
            self._proxy(b"\x89PNG\r\n\x1a\n", url="file:///etc/passwd").status_code, 400
        )


class SafeFileNameTests(TestCase):
    def test_rejects_names_that_leave_their_directory(self) -> None:
        for name in (
            "",
            ".",
            "..",
            "../x",
            "a/b",
            "a\\b",
            "..\\x",
            "C:x",
            ".active-profile",
            "a\0b",
            None,
        ):
            with self.assertRaises(UnsafeFileNameError, msg=repr(name)):
                require_safe_file_stem(name)
        for name in (
            "dQw4w9WgXcQ",
            "account_1760000000000",
            "local-song",
            "my_profile_2",
            "-abc_DEF",
        ):
            self.assertEqual(require_safe_file_stem(name), name)

    def test_custom_lyrics_cannot_be_written_outside_their_directory(self) -> None:
        root = Path(tempfile.mkdtemp())
        lyrics_dir = root / "custom_lyrics"
        lyrics_dir.mkdir()
        with patch(
            "src.lib.music.lyrics.config_dirs", SimpleNamespace(CUSTOM_LYRICS_DIR=lyrics_dir)
        ):
            with self.assertRaises(UnsafeFileNameError):
                LyricsService.save_custom("../outside", "x", "lrc")
            LyricsService.save_custom("dQw4w9WgXcQ", "x", "lrc")
            self.assertIsNone(LyricsService.get_custom("..\\outside"))
            self.assertFalse(LyricsService.delete_custom("../outside"))
        self.assertFalse((root / "outside.lrc").exists())
        self.assertTrue((lyrics_dir / "dQw4w9WgXcQ.lrc").exists())


class ProfileNameRouteTests(RouteTestCase):
    def test_profile_routes_reject_traversal_names(self) -> None:
        profiles_dir = self.root / "profiles"
        profiles_dir.mkdir()
        victim = self.root / "victim.json"
        victim.write_text("{}", encoding="utf-8")
        self.app.extensions["profile_repository"] = Profile(profiles_dir, Meta())
        with patch("src.lib.profiles.meta.config_dirs", SimpleNamespace(PROFILES_DIR=profiles_dir)):
            response = self.client.post("/profiles/delete", json={"name": "../victim"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(victim.exists())

    def test_stray_files_do_not_break_the_profile_list(self) -> None:
        profiles_dir = self.root / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "account_1.json").write_text("{}", encoding="utf-8")
        (profiles_dir / "._account_1.json").write_bytes(b"\0\5\26\7")
        with patch("src.lib.profiles.meta.config_dirs", SimpleNamespace(PROFILES_DIR=profiles_dir)):
            names = [entry["name"] for entry in Profile(profiles_dir, Meta()).list_profiles()]
        self.assertEqual(names, ["account_1"])


class ExportTargetTests(RouteTestCase):
    def test_export_only_writes_audio_files_at_absolute_paths(self) -> None:
        for output_path, fmt in (
            ("/home/user/.bashrc", "opus"),
            ("relative/song.mp3", "mp3"),
            ("/tmp/song.opus", "mp3"),
            ("/tmp/song.mp3", "exe"),
        ):
            response = self.client.post(
                "/song/export/vid", json={"output_path": output_path, "format": fmt}
            )
            self.assertEqual(response.status_code, 400, output_path)
        self.assertEqual(self.export_service.started, [])


class LogRedactionTests(TestCase):
    def test_secret_query_values_are_redacted(self) -> None:
        self.assertEqual(
            redact_secrets("[req] --> GET /remote/state?token=abc&deviceId=p from 10.0.0.2"),
            "[req] --> GET /remote/state?token=[redacted]&deviceId=p from 10.0.0.2",
        )
        self.assertEqual(
            redact_secrets('"GET /x?a=1&sk=zz HTTP/1.1" 200'),
            '"GET /x?a=1&sk=[redacted] HTTP/1.1" 200',
        )
        self.assertEqual(redact_secrets("GET /search?q=tokens"), "GET /search?q=tokens")
