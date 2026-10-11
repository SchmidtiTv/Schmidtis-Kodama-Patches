# Copyright (c) 2026 Kodama contributors
"""Exercise overlay audio demand, frame delivery, and renderer availability."""

import json
from unittest import TestCase

from src.lib.runtime.overlay import OverlayServer
from src.lib.runtime.overlay_levels import BAND_COUNT, OverlayLevels


class OverlayLevelsTests(TestCase):
    """Verify observable audio delivery without player or account access."""

    # PT009 conflicts with S101; retain the repository's unittest assertion style.

    def test_levels_keep_only_latest_frame_and_stop_demand_when_closed(self) -> None:
        """Deliver the latest frame and release demand after disconnect."""
        levels = OverlayLevels()
        self.assertEqual(levels.demand_port(), 0)  # noqa: PT009
        response = levels.stream_response()
        self.addCleanup(response.close)
        stream = iter(response.response)
        self.assertEqual(next(stream), "retry: 2000\n\n")  # noqa: PT009
        self.assertTrue(  # noqa: PT009
            levels.publish(json.dumps({"bands": [0.2] * BAND_COUNT, "level": 0.3}).encode())
        )
        self.assertTrue(  # noqa: PT009
            levels.publish(json.dumps({"bands": [0.8] * BAND_COUNT, "level": 0.9}).encode())
        )
        payload = next(stream)
        if isinstance(payload, bytes):
            payload = payload.decode()
        frame = json.loads(payload.removeprefix("data: "))
        self.assertEqual(frame["level"], 0.9)  # noqa: PT009
        response.close()
        self.assertEqual(levels.demand_port(), 0)  # noqa: PT009

    def test_levels_reject_invalid_frames(self) -> None:
        """Reject malformed frames and clamp finite values before delivery."""
        levels = OverlayLevels()
        for frame in [
            b"bad",
            b"[]",
            b'{"bands": []}',
            json.dumps({"bands": [0] * BAND_COUNT, "level": float("nan")}).encode(),
        ]:
            self.assertFalse(levels.publish(frame))  # noqa: PT009
        response = levels.stream_response()
        self.addCleanup(response.close)
        stream = iter(response.response)
        next(stream)
        self.assertTrue(  # noqa: PT009
            levels.publish(json.dumps({"bands": [3] * BAND_COUNT, "level": -2}).encode())
        )
        payload = next(stream)
        if isinstance(payload, bytes):
            payload = payload.decode()
        self.assertEqual(  # noqa: PT009
            json.loads(payload.removeprefix("data: ")), {"bands": [1] * BAND_COUNT, "level": 0}
        )

    def test_overlay_renderer_supports_reactive_shaders_and_editor_preview(self) -> None:
        """Serve the shader renderer with fresh preview content."""
        response = OverlayServer().page_response()
        self.assertTrue(response.headers["Cache-Control"].startswith("no-store"))  # noqa: PT009
        html = response.get_data(as_text=True)
        self.assertIn("SHADER_SRC", html)  # noqa: PT009
        self.assertIn("/overlay/levels", html)  # noqa: PT009
        self.assertIn("__overlayDoc", html)  # noqa: PT009
