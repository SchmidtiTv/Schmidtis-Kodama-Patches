"""System info and recent logs for the frontend Debug tab."""

import platform
import shutil
import sys
import time

from flask import jsonify

from src.config import config_dirs
from src.lib.runtime.logging import DEBUG_LOG, DEBUG_LOG_LOCK
from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session, server_start_time, stream_service


def _pkg_version(name: str) -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version(name)
    except Exception:
        return "—"


@blueprint.route("/debug/info")
def debug_info() -> RouteResponse:
    """Returns system info + last log entries for the Debug tab in the frontend."""
    node_path = shutil.which("node") or shutil.which("node.exe") or shutil.which("nodejs")

    uptime_s = int(time.time() - server_start_time())
    h, rem = divmod(uptime_s, 3600)
    m, s = divmod(rem, 60)
    uptime_str = (f"{h}h " if h else "") + f"{m}m {s}s"

    with DEBUG_LOG_LOCK:
        logs = list(DEBUG_LOG)
    session = music_session()
    refresh_age = (
        None
        if session.state.psidts_last_refresh == 0
        else int(time.time() - session.state.psidts_last_refresh)
    )

    return jsonify(
        {
            "python": sys.version.split()[0],
            "ytdlp": _pkg_version("yt-dlp"),
            "ytmusicapi": _pkg_version("ytmusicapi"),
            "flask": _pkg_version("flask"),
            "node": node_path,
            "profile": session.state.current_profile or "—",
            "platform": platform.system() + " " + platform.release(),
            "uptime": uptime_str,
            "data_dir": str(config_dirs.BASE_DIR),
            "logs": logs[-300:],
            "authed": session.state.last_authenticated,
            "cookieRefreshAgeS": refresh_age,
            "lastStreamError": stream_service().last_error,
        }
    )
