"""Development request logging for a Flask application."""

import time

from flask import Flask, Response, g, request

from src.config import Config


def setup_debug(app: Flask) -> None:
    """Register request timing hooks when debug logging is enabled."""
    if not Config.DEBUG:
        return

    app.before_request(_dbg_before)
    app.after_request(_dbg_after)
    print("[dbg] Debug logging enabled.", flush=True)


def _dbg_before() -> None:
    g.dbg_t0 = time.time()
    if request.path != "/clientlog":
        print(
            f"[req] --> {request.method} {request.full_path.rstrip('?')} from {request.remote_addr}",
            flush=True,
        )


def _dbg_after(response: Response) -> Response:
    try:
        if request.path != "/clientlog":
            started_at = getattr(g, "dbg_t0", time.time())
            elapsed_ms = (time.time() - started_at) * 1000
            print(
                f"[req] <-- {request.method} {request.path} {response.status_code} in {elapsed_ms:.0f}ms",
                flush=True,
            )
    except Exception:
        pass
    return response
