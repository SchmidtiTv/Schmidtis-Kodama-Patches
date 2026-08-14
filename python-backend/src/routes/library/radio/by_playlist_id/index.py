"""Radio (watch-playlist) endpoint."""

from flask import jsonify, request

from src.lib import YoutubeResponseMapper
from src.lib.music.audio_versions import prefer_audio_versions
from src.routes.library import blueprint
from src.routes.library._services import metadata_cache, music_session
from src.type_defs import RouteResponse


@blueprint.route("/radio/<playlist_id>")
def get_radio(playlist_id: str) -> RouteResponse:
    try:
        session = music_session()
        client = session.get_active_client()
        # A song-seeded radio has no playlist ID yet. The frontend uses "_" as the
        # route placeholder and supplies the seed in the query string instead.
        video_id = request.args.get("videoId", "").strip()
        if playlist_id == "_":
            if not video_id:
                return jsonify({"error": "videoId required"}), 400
            watch = client.get_watch_playlist(
                videoId=video_id,
                limit=50,
                radio=True,
            )
        else:
            watch = client.get_watch_playlist(
                playlistId=playlist_id,
                limit=50,
            )
        raw_tracks = watch.get("tracks") if isinstance(watch, dict) else None
        resolvable_tracks = [
            track
            for track in (raw_tracks if isinstance(raw_tracks, list) else [])
            if isinstance(track, dict) and track.get("videoId")
        ]
        tracks: list[dict[str, object]] = []
        for t in prefer_audio_versions(
            session.get_system_client(), None, resolvable_tracks, metadata_cache()
        ):
            artist_list = t.get("artists") or []
            artists = (
                ", ".join(
                    name
                    for artist in artist_list
                    if isinstance(artist, dict)
                    if isinstance(name := artist.get("name"), str)
                )
                if isinstance(artist_list, list)
                else ""
            )
            # get_watch_playlist returns thumbnail as a list of dicts OR a plain string
            thumb_raw = t.get("thumbnails") or t.get("thumbnail") or []
            if isinstance(thumb_raw, list):
                thumb = YoutubeResponseMapper.select_thumbnail(thumb_raw)
            elif isinstance(thumb_raw, str):
                thumb = thumb_raw
            else:
                thumb = ""
            album = t.get("album") or {}
            tracks.append(
                {
                    "videoId": t.get("videoId", ""),
                    "title": t.get("title", ""),
                    "artists": artists,
                    "album": album.get("name", "") if isinstance(album, dict) else "",
                    "thumbnail": thumb,
                    "duration": t.get("duration") or t.get("length", ""),
                    "isExplicit": bool(t.get("isExplicit", False)),
                }
            )
        return jsonify({"tracks": tracks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
