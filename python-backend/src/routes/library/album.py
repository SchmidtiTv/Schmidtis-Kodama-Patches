"""Album detail endpoint with a disk cache."""

from flask import jsonify, request

from src.lib import YoutubeResponseMapper
from src.lib.music.audio_versions import prefer_audio_versions
from src.type_defs import RouteResponse

from . import blueprint
from ._services import album_cache, cache_settings, metadata_cache, music_session


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
        album_tracks = album.get("tracks")
        track_items = album_tracks if isinstance(album_tracks, list) else []
        raw_tracks = [
            track for track in track_items if isinstance(track, dict) and track.get("videoId")
        ]
        raw_tracks = prefer_audio_versions(
            session.get_system_client(), None, raw_tracks, metadata_cache()
        )
        tracks = []
        raw_album_artists = album.get("artists")
        album_artists = (
            [artist for artist in raw_album_artists if isinstance(artist, dict)]
            if isinstance(raw_album_artists, list)
            else []
        )
        album_artist_name = ", ".join(a["name"] for a in album_artists)
        album_artist_browse_id = album_artists[0].get("id", "") if album_artists else ""
        for t in raw_tracks:
            raw_track_artists = t.get("artists")
            track_artists = (
                [artist for artist in raw_track_artists if isinstance(artist, dict)]
                if isinstance(raw_track_artists, list)
                else []
            )
            artists = ", ".join(a["name"] for a in track_artists) or album_artist_name
            artist_browse_id = (
                track_artists[0].get("id", "") if track_artists else album_artist_browse_id
            )
            thumbnail = YoutubeResponseMapper.select_thumbnail(album.get("thumbnails", []))
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
