"""Regression coverage for backend diagnostic version reporting."""

from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace
from unittest.mock import patch

from route_test_support import RouteTestCase


class BackendVersionTests(RouteTestCase):
    """Exercise the public health endpoint with isolated version metadata."""

    def test_status_includes_versions_without_changing_health_fields(self) -> None:
        """Installed versions accompany the existing health response."""
        with (
            patch("src.lib.runtime.versions.platform.python_version", return_value="3.12.9"),
            patch("src.lib.runtime.versions.version", side_effect=["1.12.2", "2026.09.01"]),
        ):
            response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "ok": True,
                "message": "Kodama Backend laeuft",
                "versions": {"python": "3.12.9", "ytmusicapi": "1.12.2", "ytdlp": "2026.09.01"},
            },
        )

    def test_missing_metadata_does_not_break_status(self) -> None:
        """Missing dependency metadata must not block app startup."""
        with (
            patch("src.lib.runtime.versions.version", side_effect=PackageNotFoundError),
            patch("src.lib.runtime.versions.import_module", side_effect=ImportError),
        ):
            response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["ok"])
        self.assertEqual(response.json["versions"]["ytmusicapi"], "?")
        self.assertEqual(response.json["versions"]["ytdlp"], "?")

    def test_frozen_modules_report_versions_without_metadata(self) -> None:
        """Packaged applications can use the bundled module version attributes."""
        with (
            patch("src.lib.runtime.versions.version", side_effect=PackageNotFoundError),
            patch(
                "src.lib.runtime.versions.import_module",
                side_effect=[
                    SimpleNamespace(__version__="1.12.2"),
                    SimpleNamespace(__version__="2026.09.01"),
                ],
            ),
        ):
            response = self.client.get("/status")
        self.assertEqual(response.json["versions"]["ytmusicapi"], "1.12.2")
        self.assertEqual(response.json["versions"]["ytdlp"], "2026.09.01")
