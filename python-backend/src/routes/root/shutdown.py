"""Stop the legacy local backend process."""

import os
import threading
import time

from src.type_defs import RouteResponse

from . import blueprint


@blueprint.route("/shutdown", methods=["GET", "POST"])
def shutdown() -> RouteResponse:
    def stop_process() -> None:
        time.sleep(0.2)
        os._exit(0)

    threading.Thread(target=stop_process, daemon=True).start()
    return "ok"
