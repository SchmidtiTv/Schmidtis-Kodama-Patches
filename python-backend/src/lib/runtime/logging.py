"""Console and standard-library logging setup for the backend."""

import collections
import logging
from typing import override
import sys
import threading
import time
from typing import TextIO

DEBUG_LOG = collections.deque(maxlen=500)
DEBUG_LOG_LOCK = threading.Lock()
FEEDBACK_LOG_RING = collections.deque(maxlen=300)


class LogTee:
    """Mirror complete stdout/stderr lines into the feedback log ring."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._buffer = ""

    def write(self, data: str) -> int:
        try:
            if self._stream is not None:
                self._stream.write(data)
        except Exception:
            pass

        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                FEEDBACK_LOG_RING.append(line)
        return len(data)

    def flush(self) -> None:
        try:
            if self._stream is not None:
                self._stream.flush()
        except Exception:
            pass


class _RingBufferHandler(logging.Handler):
    """Capture standard logging records for the debug endpoint."""

    @override
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = "WARN" if record.levelname == "WARNING" else record.levelname
            if level not in ("INFO", "ERROR", "WARN", "DEBUG"):
                level = "INFO"
            with DEBUG_LOG_LOCK:
                DEBUG_LOG.append(
                    {
                        "ts": time.time(),
                        "level": level,
                        "msg": self.format(record),
                        "source": "backend",
                    }
                )
        except Exception:
            pass


# Endpoints called on a timer. Their access log is never diagnostic, and at ~2 requests a
# second /overlay/push alone filled 81% of the ring — leaving bug reports with two minutes of
# it and nothing else. Dropped from the ring only; real log records are unaffected.
_NOISY_PATHS = (
    "/overlay/push",
    "/overlay/status",
    "/status",
    "/imgproxy",
    "/remote/_sync",
    "/remote/_poll",
    "/remote/_status",
)


class _DropNoisyAccessLogs(logging.Filter):
    """Keep timer-driven access log lines out of the ring without affecting real logging."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(path in message for path in _NOISY_PATHS)


_ring_handler = _RingBufferHandler()
_ring_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
_ring_handler.setLevel(logging.DEBUG)
_ring_handler.addFilter(_DropNoisyAccessLogs())


def setup_log_tee() -> None:
    """Install stdout/stderr mirrors once."""
    if not isinstance(sys.stdout, LogTee):
        sys.stdout = LogTee(sys.stdout)
    if not isinstance(sys.stderr, LogTee):
        sys.stderr = LogTee(sys.stderr)


def setup_logger() -> None:
    """Attach the shared ring-buffer handler to application and Werkzeug logs."""
    root_logger = logging.getLogger()
    werkzeug_logger = logging.getLogger("werkzeug")
    if _ring_handler not in root_logger.handlers:
        root_logger.addHandler(_ring_handler)
    if _ring_handler not in werkzeug_logger.handlers:
        werkzeug_logger.addHandler(_ring_handler)
    # The handler's own level is not enough: the root logger defaults to WARNING and discards
    # records before any handler sees them, so the backend's own logging.info() calls —
    # including per-tier timings that exist precisely to diagnose slow playback — never
    # reached the ring, and therefore never reached a bug report either.
    root_logger.setLevel(logging.INFO)
    werkzeug_logger.setLevel(logging.INFO)
