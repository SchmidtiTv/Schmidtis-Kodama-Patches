"""Artist detail page and subscribe/unsubscribe endpoints."""

from flask import jsonify, request

from src.lib import BandMemberLookupError, YoutubeResponseMapper
from src.lib.music.audio_versions import prefer_audio_versions

from . import blueprint
from ._services import band_member_finder, metadata_cache, music_session
from src.type_defs import RouteResponse


# Old server.py: _extract_artist_desc_url
def _extract_artist_desc_url(browse_id: str) -> str | None:
    """ytmusicapi keeps only the first description run, dropping the trailing
    "From Wikipedia (URL)" link run. Re-fetch and pull the real source URL out."""
    try:
        from ytmusicapi.navigation import find_object_by_key, nav, SINGLE_COLUMN_TAB, SECTION_LIST
        resp = music_session().get_active_client()._send_request("browse", {"browseId": browse_id})
        results = nav(resp, SINGLE_COLUMN_TAB + SECTION_LIST)
        shelf = find_object_by_key(results, "musicDescriptionShelfRenderer", is_key=True)
        if not shelf:
            return None
        if isinstance(shelf, dict) and "musicDescriptionShelfRenderer" in shelf:
            shelf = shelf["musicDescriptionShelfRenderer"]
        for r in shelf.get("description", {}).get("runs", []):
            url = ((r.get("navigationEndpoint") or {}).get("urlEndpoint") or {}).get("url")
            if url and "creativecommons" not in url:
                return url
    except Exception:
        pass
    return None


def _shelf_more(artist: dict, key: str) -> dict[str, str]:
    shelf = artist.get(key) or {}
    browse_id = shelf.get("browseId", "") or ""
    if browse_id.startswith("VL"):
        return {f"{key}PlaylistId": browse_id[2:], f"{key}BrowseId": "", f"{key}Params": ""}
    return {
        f"{key}PlaylistId": "",
        f"{key}BrowseId": browse_id,
        f"{key}Params": shelf.get("params", "") or "",
    }


def _video_item(video: dict, artist_name: str) -> dict[str, str]:
    artists = video.get("artists") or []
    return {
        "videoId": video.get("videoId", ""),
        "title": video.get("title", ""),
        "artists": ", ".join(artist.get("name", "") for artist in artists) or artist_name,
        "views": video.get("views", ""),
        "thumbnail": YoutubeResponseMapper.select_thumbnail(video.get("thumbnails", [])),
    }


@blueprint.route("/artist/<browse_id>")
def get_artist(browse_id: str) -> RouteResponse:
    try:
        session = music_session()
        client = session.get_active_client()
        try:
            artist = client.get_artist(browse_id)
        except KeyError as error:
            if "musicImmersiveHeaderRenderer" not in str(error):
                raise
            artist = client.get_user(browse_id)

        # Top songs
        tracks = []
        raw_tracks = [
            track
            for track in (artist.get("songs", {}).get("results", []))[:20]
            if track.get("videoId")
        ]
        for t in prefer_audio_versions(session.get_system_client(), None, raw_tracks, metadata_cache()):
            thumbnail = YoutubeResponseMapper.select_thumbnail(t.get("thumbnails", []))
            # duration may be a pre-formatted string ("3:45") or absent;
            # fall back to duration_seconds if available
            duration = t.get("duration", "")
            if not duration:
                secs = t.get("duration_seconds") or t.get("durationSeconds") or 0
                if secs:
                    m, s = divmod(int(secs), 60)
                    duration = f"{m}:{s:02d}"
            tracks.append({
                "videoId": t.get("videoId", ""),
                "title": t.get("title", ""),
                "artists": artist.get("name", ""),
                "artistBrowseId": browse_id,
                "album": (t.get("album") or {}).get("name", ""),
                "albumBrowseId": ((t.get("album") or {}).get("id") or ""),
                "duration": duration,
                "thumbnail": thumbnail,
                "isExplicit": bool(t.get("isExplicit", False)),
            })

        # Albums
        albums = []
        for a in (artist.get("albums", {}).get("results", [])):
            albums.append({
                "browseId": a.get("browseId", ""),
                "title": a.get("title", ""),
                "year": a.get("year", ""),
                "thumbnail": YoutubeResponseMapper.select_thumbnail(a.get("thumbnails", [])),
            })

        # Singles
        singles = []
        for s in (artist.get("singles", {}).get("results", [])):
            singles.append({
                "browseId": s.get("browseId", ""),
                "title": s.get("title", ""),
                "year": s.get("year", ""),
                "thumbnail": YoutubeResponseMapper.select_thumbnail(s.get("thumbnails", [])),
            })

        # Videos
        videos = []
        for v in (artist.get("videos", {}).get("results", [])):
            if not v.get("videoId"):
                continue
            videos.append(_video_item(v, artist.get("name", "")))

        playlists = []
        for playlist in (artist.get("playlists", {}).get("results", [])):
            playlists.append({
                "playlistId": playlist.get("playlistId", ""),
                "title": playlist.get("title", ""),
                "count": playlist.get("count", ""),
                "thumbnail": YoutubeResponseMapper.select_thumbnail(playlist.get("thumbnails", [])),
            })

        # Related artists ("Fans might also like")
        related = []
        for r in (artist.get("related", {}).get("results", [])):
            related.append({
                "browseId":    r.get("browseId", ""),
                "title":       r.get("title", ""),
                "subscribers": r.get("subscribers", ""),
                "thumbnail":   YoutubeResponseMapper.select_thumbnail(r.get("thumbnails", [])),
            })

        _desc = artist.get("description", "") or ""
        return jsonify({
            "name":          artist.get("name", ""),
            "thumbnail":     YoutubeResponseMapper.select_thumbnail(artist.get("thumbnails", [])),
            "description":   _desc,
            "descriptionUrl": (_extract_artist_desc_url(browse_id) if "wikipedia" in _desc.lower() else None),
            "subscribers":      artist.get("subscribers", "") or "",
            "monthlyListeners": artist.get("monthlyListeners", "") or "",
            "radioId":       artist.get("radioId", "") or "",
            "subscribed":    bool(artist.get("subscribed", False)),
            "channelId":     artist.get("channelId", "") or browse_id,
            "songsBrowseId": (lambda b: b[2:] if b.startswith("VL") else b)(artist.get("songs", {}).get("browseId", "") or ""),
            "albumsBrowseId": artist.get("albums", {}).get("browseId", "") or "",
            "albumsParams":   artist.get("albums", {}).get("params", "") or "",
            "singlesBrowseId": artist.get("singles", {}).get("browseId", "") or "",
            "singlesParams":   artist.get("singles", {}).get("params", "") or "",
            **_shelf_more(artist, "videos"),
            **_shelf_more(artist, "playlists"),
            "tracks":  tracks,
            "albums":  albums,
            "singles": singles,
            "videos":  videos,
            "playlists": playlists,
            "related": related,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/artist_videos")
def artist_videos() -> RouteResponse:
    channel_id = request.args.get("channelId", "")
    params = request.args.get("params", "")
    if not channel_id or not params:
        return jsonify({"error": "channelId and params are required"}), 400
    try:
        items = music_session().get_active_client().get_user_videos(channel_id, params)
        return jsonify({"videos": [_video_item(item, "") for item in items or [] if item.get("videoId")]})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@blueprint.route("/artist_playlists")
def artist_playlists() -> RouteResponse:
    channel_id = request.args.get("channelId", "")
    params = request.args.get("params", "")
    if not channel_id or not params:
        return jsonify({"error": "channelId and params are required"}), 400
    try:
        items = music_session().get_active_client().get_user_playlists(channel_id, params)
        return jsonify({
            "playlists": [
                {
                    "playlistId": item.get("playlistId", ""),
                    "title": item.get("title", ""),
                    "count": item.get("count", ""),
                    "thumbnail": YoutubeResponseMapper.select_thumbnail(item.get("thumbnails", [])),
                }
                for item in items or []
            ]
        })
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@blueprint.route("/artist/<browse_id>/subscribe", methods=["POST"])
def artist_subscribe(browse_id: str) -> RouteResponse:
    try:
        data = request.get_json(silent=True) or {}
        channel_id = data.get("channelId") or browse_id
        music_session().get_active_client().subscribe_artists([channel_id])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/artist/<browse_id>/members")
def artist_members(browse_id: str) -> RouteResponse:
    artist_name = request.args.get("name", "").strip()
    if not artist_name:
        return jsonify({"error": "artist name is required"}), 400
    try:
        return jsonify({"members": band_member_finder().find(artist_name)})
    except BandMemberLookupError:
        return jsonify({"error": "band members unavailable"}), 502


@blueprint.route("/artist/<browse_id>/unsubscribe", methods=["POST"])
def artist_unsubscribe(browse_id: str) -> RouteResponse:
    try:
        data = request.get_json(silent=True) or {}
        channel_id = data.get("channelId") or browse_id
        music_session().get_active_client().unsubscribe_artists([channel_id])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
