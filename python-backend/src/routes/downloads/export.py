"""Export a song to a user-chosen path, resolving the release year first."""

import os

from flask import jsonify, request

from . import blueprint
from ._services import export_service, ffmpeg, music_session
from src.type_defs import RouteResponse

# The save dialog's filters. Holding the target to an audio extension keeps a forged request
# from overwriting anything but an audio file.
_EXPORT_EXTENSIONS = {"mp3": (".mp3",), "opus": (".opus", ".webm")}


def _valid_export_target(output_path: object, fmt: object) -> bool:
    return (
        isinstance(output_path, str)
        and isinstance(fmt, str)
        and fmt in _EXPORT_EXTENSIONS
        and os.path.isabs(output_path)
        and output_path.lower().endswith(_EXPORT_EXTENSIONS[fmt])
    )


@blueprint.route("/song/export/<video_id>", methods=["POST"])
def export_audio(video_id: str) -> RouteResponse:
    service = export_service()
    data = request.get_json() or {}
    output_path = data.get("output_path", "")
    fmt = data.get("format", "opus")  # "mp3" or "opus"
    if not output_path:
        return jsonify({"error": "output_path required"}), 400
    if not _valid_export_target(output_path, fmt):
        return jsonify({"error": "invalid output_path or format"}), 400
    if service.status.get(video_id) == "exporting":
        return jsonify({"ok": True, "status": "exporting"})
    year = data.get("year", "")
    album_browse_id = data.get("albumBrowseId", "")
    print(f"Export request: video_id={video_id} fmt={fmt} year='{year}' albumBrowseId='{album_browse_id}' thumbnail='{data.get('thumbnail','')[:60]}'")
    # Try to fetch year from album data if not provided
    if not year and album_browse_id:
        try:
            album_data = music_session().get_active_client().get_album(album_browse_id)
            year = album_data.get("year", "")
            print(f"Export: fetched year={year} from album {album_browse_id}")
        except Exception as e:
            print(f"Export: failed to fetch album year: {e}")
    # Fallback: fetch song info to get year from the song's album
    if not year:
        try:
            song_info = music_session().get_active_client().get_song(video_id)
            # Try microformat for year
            mf = song_info.get("microformat", {}).get("microformatDataRenderer", {})
            upload_date = mf.get("uploadDate", "")  # e.g. "2022-06-17"
            if upload_date and len(upload_date) >= 4:
                year = upload_date[:4]
                print(f"Export: got year={year} from song upload date")
        except Exception as e:
            print(f"Export: failed to fetch song info for year: {e}")
    meta = {
        "title": data.get("title", ""),
        "artists": data.get("artists", ""),
        "album": data.get("album", ""),
        "year": year,
        "thumbnail": data.get("thumbnail", ""),
    }
    if service.start(video_id, output_path, fmt, meta) is False:
        return jsonify({"error": "export queue is full"}), 429
    return jsonify({"ok": True, "status": "exporting"})


@blueprint.route("/song/export/status/<video_id>")
def export_status(video_id: str) -> RouteResponse:
    return jsonify({"status": export_service().status.get(video_id, "not_found")})


@blueprint.route("/song/export/ffmpeg-available")
def ffmpeg_available() -> RouteResponse:
    return jsonify({"available": ffmpeg().available()})
