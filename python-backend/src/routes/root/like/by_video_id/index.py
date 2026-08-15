"""Update the liked state of a song for the active profile."""

from flask import jsonify, request

from src.lib.accounts import parse_song_rating_payload, required_id
from src.routes.account_errors import account_error_response
from src.type_defs import RouteResponse

from ... import blueprint
from ..._services import song_rating_service


@blueprint.route("/like/<video_id>", methods=["POST"])
def like_song(video_id: str) -> RouteResponse:
    try:
        data = request.get_json(silent=True)
        rating, metadata = parse_song_rating_payload(data if data is not None else {})
        normalized_video_id = required_id(video_id, "videoId")
        song_rating_service().rate(
            normalized_video_id,
            rating,
            metadata,
        )
        return jsonify({"ok": True, "rating": rating.value})
    except Exception as error:
        return account_error_response(error)
