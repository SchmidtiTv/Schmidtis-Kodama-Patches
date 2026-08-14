"""Scrobble a played track to Last.fm."""

import time

from src.type_defs import RouteResponse

from . import blueprint
from ._actions import submit_track_action


@blueprint.route("/scrobble", methods=["POST"])
def lastfm_scrobble() -> RouteResponse:
    def timestamp(data: dict[str, object]) -> dict[str, object]:
        value = data.get("timestamp")
        return (
            {"timestamp": str(int(value))}
            if isinstance(value, int | float | str)
            else {"timestamp": str(int(time.time()))}
        )

    return submit_track_action(
        "track.scrobble",
        extra=timestamp,
    )
