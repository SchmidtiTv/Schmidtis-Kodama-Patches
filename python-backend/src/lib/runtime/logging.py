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
    """Mirror complete stdout/stderr lines into the diagnostic log rings."""

    def __init__(self, stream: TextIO, level: str) -> None:
        self._stream = stream
        self._level = level
        self._buffer = ""
        self._transient = False

    def write(self, data: str) -> int:
        try:
            if self._stream is not None:
                self._stream.write(data)
        except Exception:
            pass

        self._buffer += data.replace("\r\n", "\n")
        while True:
            newline = self._buffer.find("\n")
            carriage_return = self._buffer.find("\r")
            if newline < 0 and carriage_return < 0:
                break

            split_at = (
                newline
                if carriage_return < 0 or (0 <= newline < carriage_return)
                else carriage_return
            )
            transient = split_at == carriage_return and (newline < 0 or carriage_return < newline)
            line, self._buffer = self._buffer[:split_at], self._buffer[split_at + 1 :]
            if line.strip():
                entry = {
                    "ts": time.time(),
                    "level": self._level,
                    "msg": line[:2000],
                    "source": "backend",
                }
                if self._transient and FEEDBACK_LOG_RING:
                    FEEDBACK_LOG_RING[-1] = line
                else:
                    FEEDBACK_LOG_RING.append(line)
                with DEBUG_LOG_LOCK:
                    if self._transient and DEBUG_LOG:
                        DEBUG_LOG[-1] = entry
                    else:
                        DEBUG_LOG.append(entry)
            self._transient = transient
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
        sys.stdout = LogTee(sys.stdout, "INFO")
    if not isinstance(sys.stderr, LogTee):
        sys.stderr = LogTee(sys.stderr, "ERROR")


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
