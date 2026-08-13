"""Load an artist's additional albums using YouTube Music continuation params."""

from flask import jsonify, request

from src.lib import YoutubeResponseMapper
from src.type_defs import RouteResponse

from . import blueprint
from ._services import music_session


@blueprint.route("/artist_albums")
def get_artist_albums() -> RouteResponse:
    channel_id = request.args.get("channelId", "")
    params = request.args.get("params", "")
    if not channel_id or not params:
        return jsonify({"error": "channelId and params are required"}), 400
    try:
        albums = music_session().get_active_client().get_artist_albums(channel_id, params)
        return jsonify(
            {
                "albums": [
                    {
                        "browseId": album.get("browseId", ""),
                        "title": album.get("title", ""),
                        "year": album.get("year", ""),
                        "thumbnail": YoutubeResponseMapper.select_thumbnail(
                            album.get("thumbnails", [])
                        ),
                        "type": album.get("type", ""),
                    }
                    for album in albums or []
                ]
            }
        )
    except Exception as error:
        return jsonify({"error": str(error)}), 500
