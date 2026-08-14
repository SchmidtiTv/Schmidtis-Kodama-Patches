"""Streamed (SSE) playlist loader."""

import json
from collections.abc import Iterator
from typing import cast

from flask import Response, request

from src.lib import YoutubeResponseMapper
from src.lib.music.audio_versions import iter_preferred_audio_versions
from src.lib.music.video_variants import is_video_variant
from src.routes.library import blueprint
from src.routes.library._services import (
    cache_settings,
    metadata_cache,
    music_session,
    playlist_cache,
    profiles,
)
from src.type_defs import RouteResponse

from .._formatters import format_track

_TRANSFER_CHUNK_SIZE = 200
# Audio-counterpart searches are the slow part of opening video-heavy playlists.
# Keep their batch small so the SSE response can expose the first playable tracks
# while resolution of the rest of the playlist continues.
_RESOLUTION_BATCH_SIZE = 4


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
            # SQLite. Online playlists opened from Home/Explore (RDCLAK..., PL...,
            # OLAK5...) don't exist in the local DB -- in that case fall through to
            # the online ytmusicapi fetch below instead of returning an empty
            # playlist titled with the raw ID.
            if profile_repo.is_local(profile_name):
                tracks = None
                pl_title = playlist_id
                with profile_repo.local_database(profile_name or "default") as db:
                    if playlist_id == "LM":
                        rows = db.execute(
                            "SELECT video_id, title, artists, album, thumbnail, duration FROM liked_songs ORDER BY liked_at DESC"
                        ).fetchall()
                        tracks = [
                            {
                                "videoId": r[0],
                                "setVideoId": r[0],
                                "title": r[1],
                                "artists": r[2],
                                "album": r[3],
                                "thumbnail": r[4],
                                "duration": r[5],
                            }
                            for r in rows
                        ]
                        pl_title = "Gelikte Songs"
                    else:
                        pl_row = db.execute(
                            "SELECT title FROM playlists WHERE playlist_id=?", (playlist_id,)
                        ).fetchone()
                        if pl_row:
                            pl_title = pl_row[0]
                            rows = db.execute(
                                "SELECT video_id, set_video_id, title, artists, album, thumbnail, duration FROM playlist_tracks WHERE playlist_id=? ORDER BY position ASC",
                                (playlist_id,),
                            ).fetchall()
                            tracks = [
                                {
                                    "videoId": r[0],
                                    "setVideoId": r[1],
                                    "title": r[2],
                                    "artists": r[3],
                                    "album": r[4],
                                    "thumbnail": r[5],
                                    "duration": r[6],
                                }
                                for r in rows
                            ]
                if tracks is not None:
                    yield f"data: {json.dumps({'type':'header','title':pl_title,'thumbnail':'','total':len(tracks),'cached':True})}\n\n"
                    for i in range(0, len(tracks), _TRANSFER_CHUNK_SIZE):
                        yield f"data: {json.dumps({'type':'tracks','tracks':tracks[i:i+_TRANSFER_CHUNK_SIZE]})}\n\n"
                    yield f"data: {json.dumps({'type':'done'})}\n\n"
                    return
                # Not a local playlist -> fall through to the online fetch below.

            def send(obj: object) -> str:
                return f"data: {json.dumps(obj)}\n\n"

            def serve_cached(data: dict[str, object]) -> Iterator[str]:
                tracks = cast("list[object]", data["tracks"])
                yield send(
                    {
                        "type": "header",
                        "title": data["title"],
                        "thumbnail": data["thumbnail"],
                        "total": len(tracks),
                        "cached": True,
                    }
                )
                for i in range(0, len(tracks), _TRANSFER_CHUNK_SIZE):
                    yield send({"type": "tracks", "tracks": tracks[i : i + _TRANSFER_CHUNK_SIZE]})
                yield send({"type": "done"})

            def needs_audio_resolution(data: dict[str, object]) -> bool:
                tracks = cast("list[dict[str, object]]", data.get("tracks", []))
                return any(
                    is_video_variant(track) or bool(track.get("isDetectedVideo"))
                    for track in tracks
                )

            if not force_refresh and cache_flags["playlists"]:
                # 1. In-memory cache (fastest) -- skip if missing isExplicit field
                mem = cache.get_memory(playlist_id, profile_name)
                if mem is not None:
                    mem_tracks = cast("list[dict[str, object]]", mem.get("tracks", []))
                    if (mem_tracks and "isExplicit" not in mem_tracks[0]) or needs_audio_resolution(
                        mem
                    ):
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
                yield send(
                    {"type": "loading", "message": "Liked Songs werden abgerufen…", "progress": 0}
                )
                songs = session.get_active_client().get_liked_songs()
                raw_tracks = [track for track in songs.get("tracks", []) if track.get("videoId")]
                total = len(raw_tracks)
                yield send(
                    {"type": "header", "title": "Liked Songs", "thumbnail": "", "total": total}
                )
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
                data: dict[str, object] = {
                    "title": "Liked Songs",
                    "thumbnail": "",
                    "tracks": all_tracks,
                }
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

            yield send(
                {
                    "type": "header",
                    "title": playlist.get("title", ""),
                    "thumbnail": thumbnail,
                    "total": total,
                }
            )
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
            data: dict[str, object] = {
                "title": playlist.get("title", ""),
                "thumbnail": thumbnail,
                "tracks": all_tracks,
            }
            if cache_flags["playlists"]:
                cache.put(playlist_id, profile_name, data)
                cache.save_playlist_disk(playlist_id, profile_name, data)
            yield send({"type": "done"})

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )
