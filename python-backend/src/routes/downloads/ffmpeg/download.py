"""Stream progress while downloading the managed FFmpeg binary."""

from flask import Response, request

from src.type_defs import RouteResponse

from .. import blueprint
from .._services import ffmpeg


@blueprint.route("/ffmpeg/download")
def ffmpeg_download() -> RouteResponse:
    # Read the flag here — the request context isn't live inside the generator.
    force = request.args.get("force") == "1"
    return Response(
        ffmpeg().download_stream(force),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
