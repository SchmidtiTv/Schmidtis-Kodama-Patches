"""Album detail endpoint with a disk cache."""

from flask import jsonify, request

from src.lib import AlbumDetailsError, YoutubeResponseMapper
from src.lib.music.audio_versions import prefer_audio_versions

from . import blueprint
from ._services import (
    album_cache,
    album_details_finder,
    cache_settings,
    metadata_cache,
    music_session,
)
from src.type_defs import RouteResponse


@blueprint.route("/album/<browse_id>")
def get_album(browse_id: str) -> RouteResponse:
    try:
        cache = album_cache()
        cache_flags = cache_settings().enabled
        force_refresh = request.args.get("refresh", "0") == "1"
        if not force_refresh and cache_flags["albums"]:
            cached = cache.load_album_disk(browse_id)
            if cached:
                return jsonify(cached)

        session = music_session()
        client = session.get_active_client()
        album = client.get_album(browse_id)
        raw_tracks = [track for track in album.get("tracks", []) if track.get("videoId")]
        raw_tracks = prefer_audio_versions(
            session.get_system_client(), None, raw_tracks, metadata_cache()
        )
        tracks = []
        album_artists = album.get("artists", [])
        album_artist_name = ", ".join(a["name"] for a in album_artists)
        album_artist_browse_id = album_artists[0].get("id", "") if album_artists else ""
        # Album-level constant — computed once instead of once per track.
        thumbnail = YoutubeResponseMapper.select_thumbnail(album.get("thumbnails", []))
        for t in raw_tracks:
            track_artists = t.get("artists", [])
            artists = ", ".join(a["name"] for a in track_artists) or album_artist_name
            artist_browse_id = (
                track_artists[0].get("id", "") if track_artists else album_artist_browse_id
            )
            tracks.append(
                {
                    "videoId": t.get("videoId", ""),
                    "title": t.get("title", ""),
                    "artists": artists,
                    "artistBrowseId": artist_browse_id,
                    "artistLinks": YoutubeResponseMapper.build_artist_links(
                        track_artists or album_artists
                    ),
                    "album": album.get("title", ""),
                    "duration": t.get("duration", ""),
                    "thumbnail": thumbnail,
                    "isExplicit": bool(t.get("isExplicit", False)),
                }
            )
        result = {
            "title": album.get("title", ""),
            "artists": album_artist_name,
            "artistBrowseId": album_artist_browse_id,
            "year": album.get("year", ""),
            "thumbnail": YoutubeResponseMapper.select_thumbnail(album.get("thumbnails", [])),
            "tracks": tracks,
        }
        if cache_flags["albums"]:
            cache.save_album_disk(browse_id, result)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/album/<browse_id>/musicbrainz")
def get_album_musicbrainz_details(browse_id: str) -> RouteResponse:
    artist = request.args.get("artist", "").strip()
    album = request.args.get("album", "").strip()
    if not artist or not album:
        return jsonify({"error": "artist and album are required"}), 400
    try:
        details = album_details_finder().find(artist, album)
    except AlbumDetailsError:
        return jsonify({"error": "album details unavailable"}), 502
    if details is None:
        return jsonify({"error": "no matching release found"}), 404
    return jsonify(details)
