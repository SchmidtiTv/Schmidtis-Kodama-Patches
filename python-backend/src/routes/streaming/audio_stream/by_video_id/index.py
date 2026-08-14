"""Progressive range-forwarding audio proxy."""

from flask import Response, jsonify, request

from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import stream_service


@blueprint.route("/audio-stream/<video_id>")
def audio_stream(video_id: str) -> RouteResponse:
    service = stream_service()
    upstream, error = service.open_audio_stream(video_id, request.headers.get("Range"))
    if error is not None:
        payload, status = error
        return jsonify(payload), status
    if upstream is None:
        return jsonify({"error": "stream unavailable"}), 502

    headers = service.build_proxy_headers(upstream)
    content_type = upstream.headers.get("Content-Type", "audio/mp4")
    return Response(
        service.iter_upstream(upstream),
        status=upstream.status_code,
        headers=headers,
        content_type=content_type,
    )
