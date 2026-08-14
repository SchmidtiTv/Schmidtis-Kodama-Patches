"""Track normalization shared by the playlist fetch and stream endpoints."""

from typing import cast

from src.lib import YoutubeResponseMapper
from src.lib.music.video_variants import has_video_thumbnail, video_evidence


# Old server.py: the `fmt` closure in stream_playlist / the track loop in get_playlist
def format_track(track: dict[str, object]) -> dict[str, object]:
    """Full track object as returned by /playlist/<id> and /playlist/<id>/stream."""
    artist_list = cast("list[dict[str, str]]", track.get("artists", []))
    artists = ", ".join(a["name"] for a in artist_list)
    artist_browse_id = (artist_list[0].get("id") or "") if artist_list else ""
    album = cast("dict[str, str]", track.get("album") or {})
    thumbnails = cast(
        "list[dict[str, object]]", track.get("thumbnails") or track.get("thumbnail") or []
    )
    normalized_track = {**track, "thumbnails": thumbnails}
    evidence = video_evidence(normalized_track)
    video_type = str(track.get("videoType", ""))
    thumbnail_dimensions = [
        f"{thumb.get('width')}x{thumb.get('height')}"
        for thumb in thumbnails
        if isinstance(thumb.get("width"), int) and isinstance(thumb.get("height"), int)
    ]
    if evidence:
        print(
            "[playlist] video variant detected "
            f"video_id={track.get('videoId', '')} title={track.get('title', '')!r} "
            f"evidence={','.join(evidence)} raw_video_type={video_type or 'missing'} "
            f"thumbnail_dimensions={thumbnail_dimensions or ['unknown']}",
            flush=True,
        )
    return {
        "videoId": track.get("videoId", ""),
        "setVideoId": track.get("setVideoId", ""),
        "title": track.get("title", ""),
        "artists": artists,
        "artistBrowseId": artist_browse_id,
        "artistLinks": YoutubeResponseMapper.build_artist_links(artist_list),
        "album": album.get("name", ""),
        "albumBrowseId": (album.get("id") or ""),
        "duration": track.get("duration") or track.get("length", ""),
        "thumbnail": YoutubeResponseMapper.select_thumbnail(thumbnails),
        "hasVideoThumbnail": has_video_thumbnail(normalized_track),
        "isDetectedVideo": bool(evidence),
        "videoEvidence": evidence,
        "videoType": video_type,
        "thumbnailDimensions": thumbnail_dimensions,
        "isExplicit": bool(track.get("isExplicit", False)),
    }
