"""Stop the legacy local backend process."""

import os
import threading
import time

from . import blueprint
from src.type_defs import RouteResponse


# POST only: a GET could be fired by any web page through an <img> tag.
@blueprint.route("/shutdown", methods=["POST"])
def shutdown() -> RouteResponse:
    def stop_process() -> None:
        time.sleep(0.2)
        os._exit(0)

    threading.Thread(target=stop_process, daemon=True).start()
    return "ok"
