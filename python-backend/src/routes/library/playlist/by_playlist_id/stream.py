"""SSE adapter for streamed playlist loading."""

import json
from collections.abc import Iterator

from flask import Response, current_app, request

from src.lib.accounts import AccountError, required_id
from src.routes.library import blueprint
from src.routes.library._services import playlist_service
from src.type_defs import RouteResponse


@blueprint.route("/playlist/<playlist_id>/stream")
def stream_playlist(playlist_id: str) -> RouteResponse:
    force_refresh = request.args.get("refresh", "0") == "1"
    logger = current_app.logger
    service = playlist_service()

    def generate() -> Iterator[str]:
        events: Iterator[dict[str, object]] | None = None
        try:
            normalized_id = required_id(playlist_id, "playlistId")
            events = service.stream(
                normalized_id,
                force_refresh=force_refresh,
            )
            for event in events:
                yield _sse(event)
        except GeneratorExit:
            if events is not None and hasattr(events, "close"):
                events.close()
            raise
        except AccountError as error:
            yield _sse({"type": "error", "message": error.safe_message})
        except Exception:
            logger.exception("Unexpected playlist stream failure")
            yield _sse({"type": "error", "message": "Playlist loading failed."})

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event)}\n\n"
