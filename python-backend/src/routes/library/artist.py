"""Artist detail page and subscribe/unsubscribe endpoints."""

from flask import jsonify, request

from src.lib import BandMemberLookupError, YoutubeResponseMapper
from src.lib.music.audio_versions import prefer_audio_versions
from src.type_defs import RouteResponse

from . import blueprint
from ._services import band_member_finder, metadata_cache, music_session


def _payload_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _payload_dicts(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


# Old server.py: _extract_artist_desc_url
def _extract_artist_desc_url(browse_id: str) -> str | None:
    """Ytmusicapi keeps only the first description run, dropping the trailing
    "From Wikipedia (URL)" link run. Re-fetch and pull the real source URL out.
    """
    try:
        from ytmusicapi.navigation import SECTION_LIST, SINGLE_COLUMN_TAB, find_object_by_key, nav

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


@blueprint.route("/artist/<browse_id>")
def get_artist(browse_id: str) -> RouteResponse:
    try:
        session = music_session()
        client = session.get_active_client()
        artist = client.get_artist(browse_id)

        # Top songs
        tracks = []
        songs = _payload_dict(artist.get("songs"))
        raw_tracks = [
            track for track in _payload_dicts(songs.get("results"))[:20] if track.get("videoId")
        ]
        for t in prefer_audio_versions(
            session.get_system_client(), None, raw_tracks, metadata_cache()
        ):
            thumbnail = YoutubeResponseMapper.select_thumbnail(t.get("thumbnails", []))
            # duration may be a pre-formatted string ("3:45") or absent;
            # fall back to duration_seconds if available
            duration = t.get("duration", "")
            if not duration:
                secs = t.get("duration_seconds") or t.get("durationSeconds")
                if isinstance(secs, (int, str)) and str(secs).isdigit():
                    m, s = divmod(int(secs), 60)
                    duration = f"{m}:{s:02d}"
            album = _payload_dict(t.get("album"))
            tracks.append(
                {
                    "videoId": t.get("videoId", ""),
                    "title": t.get("title", ""),
                    "artists": artist.get("name", ""),
                    "artistBrowseId": browse_id,
                    "album": album.get("name", ""),
                    "albumBrowseId": album.get("id") or "",
                    "duration": duration,
                    "thumbnail": thumbnail,
                    "isExplicit": bool(t.get("isExplicit", False)),
                }
            )

        # Albums
        albums = []
        albums_payload = _payload_dict(artist.get("albums"))
        for a in _payload_dicts(albums_payload.get("results")):
            albums.append(
                {
                    "browseId": a.get("browseId", ""),
                    "title": a.get("title", ""),
                    "year": a.get("year", ""),
                    "thumbnail": YoutubeResponseMapper.select_thumbnail(a.get("thumbnails", [])),
                }
            )

        # Singles
        singles = []
        singles_payload = _payload_dict(artist.get("singles"))
        for s in _payload_dicts(singles_payload.get("results")):
            singles.append(
                {
                    "browseId": s.get("browseId", ""),
                    "title": s.get("title", ""),
                    "year": s.get("year", ""),
                    "thumbnail": YoutubeResponseMapper.select_thumbnail(s.get("thumbnails", [])),
                }
            )

        # Videos
        videos = []
        videos_payload = _payload_dict(artist.get("videos"))
        for v in _payload_dicts(videos_payload.get("results")):
            if not v.get("videoId"):
                continue
            v_artists = _payload_dicts(v.get("artists"))
            videos.append(
                {
                    "videoId": v.get("videoId", ""),
                    "title": v.get("title", ""),
                    "artists": ", ".join(str(a.get("name") or "") for a in v_artists)
                    or artist.get("name", ""),
                    "views": v.get("views", ""),
                    "thumbnail": YoutubeResponseMapper.select_thumbnail(v.get("thumbnails", [])),
                }
            )

        # Related artists ("Fans might also like")
        related = []
        related_payload = _payload_dict(artist.get("related"))
        for r in _payload_dicts(related_payload.get("results")):
            related.append(
                {
                    "browseId": r.get("browseId", ""),
                    "title": r.get("title", ""),
                    "subscribers": r.get("subscribers", ""),
                    "thumbnail": YoutubeResponseMapper.select_thumbnail(r.get("thumbnails", [])),
                }
            )

        _desc = artist.get("description", "") or ""
        return jsonify(
            {
                "name": artist.get("name", ""),
                "thumbnail": YoutubeResponseMapper.select_thumbnail(artist.get("thumbnails", [])),
                "description": _desc,
                "descriptionUrl": (
                    _extract_artist_desc_url(browse_id) if "wikipedia" in _desc.lower() else None
                ),
                "subscribers": artist.get("subscribers", "") or "",
                "monthlyListeners": artist.get("monthlyListeners", "") or "",
                "radioId": artist.get("radioId", "") or "",
                "subscribed": bool(artist.get("subscribed", False)),
                "channelId": artist.get("channelId", "") or browse_id,
                "songsBrowseId": str(songs.get("browseId") or "").removeprefix("VL"),
                "albumsBrowseId": albums_payload.get("browseId") or "",
                "albumsParams": albums_payload.get("params") or "",
                "singlesBrowseId": singles_payload.get("browseId") or "",
                "singlesParams": singles_payload.get("params") or "",
                "tracks": tracks,
                "albums": albums,
                "singles": singles,
                "videos": videos,
                "related": related,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
