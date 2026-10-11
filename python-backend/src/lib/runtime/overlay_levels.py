# Copyright (c) 2026 Kodama contributors
"""Demand-driven live audio frames for reactive OBS layers."""

import json
import math
import socket
import threading
from collections.abc import Generator

from flask import Response

BAND_COUNT = 48


class OverlayLevels:
    """Own audio-frame delivery and listener demand for one application."""

    def __init__(self) -> None:
        """Initialize the latest-frame channel without opening a socket."""
        self._condition = threading.Condition()
        self._sequence = 0
        self._data = ""
        self._clients = 0
        self._port = 0

    def demand_port(self) -> int:
        """Return a localhost UDP port only while an overlay listens."""
        with self._condition:
            if not self._clients:
                return 0
            if self._port:
                return self._port
            receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                receiver.bind(("127.0.0.1", 0))
            except OSError:
                receiver.close()
                raise
            self._port = receiver.getsockname()[1]
            threading.Thread(
                target=self._receive, args=(receiver,), daemon=True, name="kodama-overlay-levels"
            ).start()
            return self._port

    def _receive(self, receiver: socket.socket) -> None:
        while True:
            try:
                packet = receiver.recv(8192)
            except OSError:
                receiver.close()
                return
            self.publish(packet)

    def publish(self, packet: bytes) -> bool:
        """Validate a datagram and replace the latest audio frame."""
        try:
            frame = json.loads(packet)
        except (ValueError, UnicodeDecodeError):
            return False
        if not isinstance(frame, dict):
            return False
        bands = frame.get("bands")
        level = frame.get("level")
        if not isinstance(bands, list) or len(bands) != BAND_COUNT:
            return False
        values = [*bands, level]
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
            for v in values
        ):
            return False
        if not isinstance(level, (int, float)):
            return False
        data = json.dumps(
            {"bands": [max(0, min(1, v)) for v in bands], "level": max(0, min(1, level))}
        )
        with self._condition:
            self._sequence += 1
            self._data = data
            self._condition.notify_all()
        return True

    def stream_response(self) -> Response:
        """Stream the newest frame, skipping superseded frames for slow clients."""

        def frames() -> Generator[str, None, None]:
            with self._condition:
                self._clients += 1
                sequence = self._sequence
            try:
                yield "retry: 2000\n\n"
                while True:
                    with self._condition:
                        fresh = self._condition.wait_for(
                            lambda previous=sequence: self._sequence != previous, timeout=5
                        )
                        sequence, data = self._sequence, self._data
                    yield "data: " + data + "\n\n" if fresh and data else ": ping\n\n"
            finally:
                with self._condition:
                    self._clients -= 1

        return Response(
            frames(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )
