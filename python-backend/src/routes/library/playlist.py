"""Playlist create/edit/delete, fetch, and the streamed (SSE) playlist loader."""

import json
import time
import uuid
from collections.abc import Iterator
from typing import cast

from flask import Response, jsonify, request

from src.lib import YoutubeResponseMapper
from src.lib.music.audio_versions import iter_preferred_audio_versions, prefer_audio_versions
from src.lib.music.video_variants import is_video_variant

from . import blueprint
from ._formatters import format_track
from ._services import cache_settings, metadata_cache, music_session, playlist_cache, profiles
from src.type_defs import RouteResponse


_TRANSFER_CHUNK_SIZE = 200
# Audio-counterpart searches are the slow part of opening video-heavy playlists.
# Keep their batch small so the SSE response can expose the first playable tracks
# while resolution of the rest of the playlist continues.
_RESOLUTION_BATCH_SIZE = 4


@blueprint.route("/playlist/create", methods=["POST"])
def create_playlist() -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        if not title:
            return jsonify({"error": "Title is required"}), 400
        description = data.get("description", "")
        privacy = data.get("privacyStatus", "PRIVATE")
        if profile_repo.is_local(profile_name):
            playlist_id = str(uuid.uuid4())
            now = int(time.time())
            with profile_repo.local_database(profile_name or "default") as db:
                db.execute(
                    "INSERT INTO playlists (playlist_id, title, description, privacy, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (playlist_id, title, description, privacy, now, now)
                )
                db.commit()
            return jsonify({"ok": True, "playlistId": playlist_id})
        video_ids = data.get("videoIds")
        result = session.get_active_client().create_playlist(title, description, privacy_status=privacy, video_ids=video_ids)
        return jsonify({"ok": True, "playlistId": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/playlist/<playlist_id>/add", methods=["POST"])
def playlist_add_tracks(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        data = request.get_json() or {}
        video_ids = data.get("videoIds", [])
        if not video_ids:
            return jsonify({"error": "videoIds required"}), 400
        if profile_repo.is_local(profile_name):
            tracks_meta = {t["videoId"]: t for t in data.get("tracks", []) if "videoId" in t}
            now = int(time.time())
            with profile_repo.local_database(profile_name or "default") as db:
                max_pos = db.execute("SELECT COALESCE(MAX(position),0) FROM playlist_tracks WHERE playlist_id=?", (playlist_id,)).fetchone()[0]
                for i, vid in enumerate(video_ids):
                    meta = tracks_meta.get(vid, {})
                    svid = str(uuid.uuid4())
                    db.execute(
                        "INSERT INTO playlist_tracks (playlist_id, video_id, title, artists, album, thumbnail, duration, set_video_id, position, added_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (playlist_id, vid, meta.get("title",""), meta.get("artists",""),
                         meta.get("album",""), meta.get("thumbnail",""), meta.get("duration",""),
                         svid, max_pos + i + 1, now)
                    )
                db.execute("UPDATE playlists SET updated_at=? WHERE playlist_id=?", (now, playlist_id))
                db.commit()
            return jsonify({"ok": True})
        session.get_active_client().add_playlist_items(playlist_id, video_ids)
        playlist_cache().purge_playlist_cache(playlist_id, profile_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/playlist/<playlist_id>/remove", methods=["POST"])
def playlist_remove_tracks(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        data = request.get_json() or {}
        videos = data.get("videos", [])
        if not videos:
            return jsonify({"error": "videos required"}), 400
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                for v in videos:
                    svid = v.get("setVideoId")
                    if svid:
                        db.execute("DELETE FROM playlist_tracks WHERE playlist_id=? AND set_video_id=?", (playlist_id, svid))
                    else:
                        db.execute("DELETE FROM playlist_tracks WHERE playlist_id=? AND video_id=?", (playlist_id, v.get("videoId","")))
                db.execute("UPDATE playlists SET updated_at=? WHERE playlist_id=?", (int(time.time()), playlist_id))
                db.commit()
            return jsonify({"ok": True})
        session.get_active_client().remove_playlist_items(playlist_id, videos)
        playlist_cache().purge_playlist_cache(playlist_id, profile_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/playlist/<playlist_id>/edit", methods=["POST"])
def playlist_edit(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        data = request.get_json() or {}
        title = data.get("title")
        description = data.get("description")
        privacy = data.get("privacyStatus")
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                if title:
                    db.execute("UPDATE playlists SET title=?, updated_at=? WHERE playlist_id=?", (title, int(time.time()), playlist_id))
                if description is not None:
                    db.execute("UPDATE playlists SET description=? WHERE playlist_id=?", (description, playlist_id))
                if privacy:
                    db.execute("UPDATE playlists SET privacy=? WHERE playlist_id=?", (privacy, playlist_id))
                db.commit()
            return jsonify({"ok": True})
        session.get_active_client().edit_playlist(playlist_id, title=title, description=description, privacyStatus=privacy)
        playlist_cache().purge_playlist_cache(playlist_id, profile_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/playlist/<playlist_id>", methods=["DELETE"])
def delete_playlist(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    try:
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                db.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
                db.execute("DELETE FROM playlists WHERE playlist_id=?", (playlist_id,))
                db.commit()
            return jsonify({"ok": True})
        session.get_active_client().delete_playlist(playlist_id)
        playlist_cache().purge_playlist_cache(playlist_id, profile_name)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/playlist/<playlist_id>/stream")
def stream_playlist(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    resolver = session.get_system_client()
    cache = playlist_cache()
    counterpart_cache = metadata_cache()
    cache_flags = cache_settings().enabled
    force_refresh = request.args.get("refresh", "0") == "1"

    def generate() -> Iterator[str]:
        try:
            # Local profile: serve locally-owned playlists (and Liked Songs) from
            # SQLite. Online playlists opened from Home/Explore (RDCLAK…, PL…,
            # OLAK5…) don't exist in the local DB — in that case fall through to
            # the online ytmusicapi fetch below instead of returning an empty
            # playlist titled with the raw ID.
            if profile_repo.is_local(profile_name):
                tracks = None
                pl_title = playlist_id
                pl_description = ""
                with profile_repo.local_database(profile_name or "default") as db:
                    if playlist_id == "LM":
                        rows = db.execute(
                            "SELECT video_id, title, artists, album, thumbnail, duration FROM liked_songs ORDER BY liked_at DESC"
                        ).fetchall()
                        tracks = [{"videoId": r[0], "setVideoId": r[0], "title": r[1], "artists": r[2],
                                   "album": r[3], "thumbnail": r[4], "duration": r[5]} for r in rows]
                        pl_title = "Gelikte Songs"
                    else:
                        pl_row = db.execute("SELECT title, description FROM playlists WHERE playlist_id=?", (playlist_id,)).fetchone()
                        if pl_row:
                            pl_title = pl_row[0]
                            pl_description = pl_row[1] or ""
                            rows = db.execute(
                                "SELECT video_id, set_video_id, title, artists, album, thumbnail, duration FROM playlist_tracks WHERE playlist_id=? ORDER BY position ASC",
                                (playlist_id,)
                            ).fetchall()
                            tracks = [{"videoId": r[0], "setVideoId": r[1], "title": r[2], "artists": r[3],
                                       "album": r[4], "thumbnail": r[5], "duration": r[6]} for r in rows]
                if tracks is not None:
                    yield f"data: {json.dumps({'type':'header','title':pl_title,'description':pl_description,'thumbnail':'','total':len(tracks),'cached':True})}\n\n"
                    for i in range(0, len(tracks), _TRANSFER_CHUNK_SIZE):
                        yield f"data: {json.dumps({'type':'tracks','tracks':tracks[i:i+_TRANSFER_CHUNK_SIZE]})}\n\n"
                    yield f"data: {json.dumps({'type':'done'})}\n\n"
                    return
                # Not a local playlist → fall through to the online fetch below.

            def send(obj: object) -> str:
                return f"data: {json.dumps(obj)}\n\n"

            def serve_cached(data: dict[str, object]) -> Iterator[str]:
                tracks = cast(list[object], data["tracks"])
                yield send({"type": "header", "title": data["title"], "description": data.get("description", ""), "thumbnail": data["thumbnail"], "total": len(tracks), "cached": True})
                for i in range(0, len(tracks), _TRANSFER_CHUNK_SIZE):
                    yield send({"type": "tracks", "tracks": tracks[i:i+_TRANSFER_CHUNK_SIZE]})
                yield send({"type": "done"})

            def needs_audio_resolution(data: dict[str, object]) -> bool:
                tracks = cast(list[dict[str, object]], data.get("tracks", []))
                return any(
                    is_video_variant(track) or bool(track.get("isDetectedVideo"))
                    for track in tracks
                )

            if not force_refresh and cache_flags["playlists"]:
                # 1. In-memory cache (fastest) — skip if missing isExplicit field
                mem = cache.get_memory(playlist_id, profile_name)
                if mem is not None:
                    mem_tracks = cast(list[dict[str, object]], mem.get("tracks", []))
                    if (mem_tracks and "isExplicit" not in mem_tracks[0]) or needs_audio_resolution(mem):
                        cache.discard_memory(playlist_id, profile_name)
                    else:
                        yield from serve_cached(mem)
                        return
                # 2. Disk cache
                disk = cache.load_playlist_disk(playlist_id, profile_name)
                if disk and not needs_audio_resolution(disk):
                    cache.put(playlist_id, profile_name, disk)  # warm in-memory cache too
                    yield from serve_cached(disk)
                    return

            if playlist_id == "LM":
                yield send({"type": "loading", "message": "Liked Songs werden abgerufen…", "progress": 0})
                songs = session.get_active_client().get_liked_songs()
                raw_tracks = [track for track in songs.get("tracks", []) if track.get("videoId")]
                total = len(raw_tracks)
                yield send({"type": "header", "title": "Liked Songs", "thumbnail": "", "total": total})
                all_tracks: list[dict[str, object]] = []
                for raw_batch in iter_preferred_audio_versions(
                    resolver,
                    None,
                    raw_tracks,
                    _RESOLUTION_BATCH_SIZE,
                    counterpart_cache,
                ):
                    formatted_batch = [format_track(track) for track in raw_batch]
                    all_tracks.extend(formatted_batch)
                    pct = min(100, round(len(all_tracks) / total * 100)) if total else 100
                    yield send({"type": "progress", "progress": pct})
                    yield send({"type": "tracks", "tracks": formatted_batch})
                data: dict[str, object] = {"title": "Liked Songs", "thumbnail": "", "tracks": all_tracks}
                if cache_flags["playlists"]:
                    cache.put(playlist_id, profile_name, data)
                    cache.save_playlist_disk(playlist_id, profile_name, data)
                yield send({"type": "done"})
                return

            yield send({"type": "loading", "message": "Playlist wird abgerufen…", "progress": 0})
            playlist = session.get_active_client().get_playlist(playlist_id, limit=None)
            thumbs = playlist.get("thumbnails") or []
            thumbnail = YoutubeResponseMapper.select_thumbnail(thumbs)
            raw_tracks = [t for t in playlist.get("tracks", []) if t.get("videoId")]
            total = len(raw_tracks)

            description = playlist.get("description", "") or ""
            yield send({"type": "header", "title": playlist.get("title", ""), "description": description, "thumbnail": thumbnail, "total": total})
            all_tracks: list[dict[str, object]] = []
            for raw_batch in iter_preferred_audio_versions(
                resolver,
                playlist_id,
                raw_tracks,
                _RESOLUTION_BATCH_SIZE,
                counterpart_cache,
            ):
                formatted_batch = [format_track(track) for track in raw_batch]
                all_tracks.extend(formatted_batch)
                pct = min(100, round(len(all_tracks) / total * 100)) if total else 100
                yield send({"type": "progress", "progress": pct})
                yield send({"type": "tracks", "tracks": formatted_batch})
            data: dict[str, object] = {"title": playlist.get("title", ""), "description": description, "thumbnail": thumbnail, "tracks": all_tracks}
            if cache_flags["playlists"]:
                cache.put(playlist_id, profile_name, data)
                cache.save_playlist_disk(playlist_id, profile_name, data)
            yield send({"type": "done"})

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Transfer-Encoding": "chunked"}
    )


@blueprint.route("/playlist/<playlist_id>")
def get_playlist(playlist_id: str) -> RouteResponse:
    session = music_session()
    profile_repo = profiles()
    profile_name = session.state.current_profile
    resolver = session.get_system_client()
    try:
        if profile_repo.is_local(profile_name):
            with profile_repo.local_database(profile_name or "default") as db:
                if playlist_id == "LM":
                    rows = db.execute(
                        "SELECT video_id, title, artists, album, thumbnail, duration FROM liked_songs ORDER BY liked_at DESC"
                    ).fetchall()
                    tracks = [{"videoId": r[0], "setVideoId": r[0], "title": r[1], "artists": r[2],
                               "album": r[3], "thumbnail": r[4], "duration": r[5]} for r in rows]
                    return jsonify({"title": "Gelikte Songs", "thumbnail": "", "tracks": tracks})
                pl_row = db.execute("SELECT title FROM playlists WHERE playlist_id=?", (playlist_id,)).fetchone()
                rows = None
                if pl_row:
                    rows = db.execute(
                        "SELECT video_id, set_video_id, title, artists, album, thumbnail, duration FROM playlist_tracks WHERE playlist_id=? ORDER BY position ASC",
                        (playlist_id,)
                    ).fetchall()
            if pl_row and rows is not None:
                tracks = [{"videoId": r[0], "setVideoId": r[1], "title": r[2], "artists": r[3],
                           "album": r[4], "thumbnail": r[5], "duration": r[6]} for r in rows]
                return jsonify({"title": pl_row[0], "thumbnail": "", "tracks": tracks})
            # Not a local playlist → fall through to the online fetch below.

        # "LM" is the special Liked Songs playlist
        if playlist_id == "LM":
            songs = session.get_active_client().get_liked_songs()
            raw_tracks = [track for track in songs.get("tracks", []) if track.get("videoId")]
            tracks = [format_track(track) for track in prefer_audio_versions(
                resolver, None, raw_tracks, metadata_cache()
            )]
            return jsonify({"title": "Liked Songs", "thumbnail": "", "tracks": tracks})

        playlist = session.get_active_client().get_playlist(playlist_id, limit=None)
        raw_tracks = [t for t in playlist.get("tracks", []) if t.get("videoId")]
        raw_tracks = prefer_audio_versions(
            resolver, playlist_id, raw_tracks, metadata_cache()
        )
        tracks = [format_track(t) for t in raw_tracks]
        return jsonify({
            "title": playlist.get("title", ""),
            "thumbnail": (playlist.get("thumbnails") or [{}])[-1].get("url", ""),
            "tracks": tracks,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
