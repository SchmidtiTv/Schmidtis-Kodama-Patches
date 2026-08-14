"""Public song statistics endpoint."""

import requests
from flask import jsonify

from src.routes.library import blueprint
from src.type_defs import RouteResponse


def _format_count(count: int | None) -> str | None:
    if count is None:
        return None
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


@blueprint.route("/song/stats/<video_id>")
def song_stats(video_id: str) -> RouteResponse:
    try:
        response = requests.get(
            f"https://returnyoutubedislikeapi.com/votes?videoId={video_id}",
            timeout=5,
            headers={"Accept": "application/json"},
        )
        if response.status_code == 200:
            data = response.json()
            return jsonify(
                {
                    "views": _format_count(data.get("viewCount")),
                    "likes": _format_count(data.get("likes")),
                    "dislikes": _format_count(data.get("dislikes")),
                    "viewsRaw": data.get("viewCount"),
                    "likesRaw": data.get("likes"),
                    "dislikesRaw": data.get("dislikes"),
                }
            )
        return jsonify({"error": "stats unavailable"}), 502
    except Exception as error:
        return jsonify({"error": str(error)}), 500
