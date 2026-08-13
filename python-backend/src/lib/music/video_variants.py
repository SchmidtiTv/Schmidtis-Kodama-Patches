"""Signals shared by video detection and audio-counterpart resolution."""

import re
from collections.abc import Mapping

VIDEO_TYPES = {"MUSIC_VIDEO_TYPE_OMV", "MUSIC_VIDEO_TYPE_UGC"}

_VIDEO_TITLE_MARKER = re.compile(
    r"\s*[\[(](?:official(?:\s+(?:hd|music))?|music|lyric)\s+video[\])]\s*$",
    re.IGNORECASE,
)


def has_video_thumbnail(track: Mapping[str, object]) -> bool:
    """Return whether a track has a reliably wide video thumbnail."""
    raw_thumbnails = track.get("thumbnails") or track.get("thumbnail") or []
    if not isinstance(raw_thumbnails, list):
        return False
    return any(
        isinstance(thumb, dict)
        and isinstance(thumb.get("width"), int)
        and isinstance(thumb.get("height"), int)
        and thumb["width"] > thumb["height"] * 1.15
        for thumb in raw_thumbnails
    )


def has_video_title_marker(track: Mapping[str, object]) -> bool:
    """Return whether the title explicitly labels the entry as a video."""
    return bool(_VIDEO_TITLE_MARKER.search(str(track.get("title", ""))))


def video_evidence(track: Mapping[str, object]) -> list[str]:
    """Return concrete video signals, excluding the raw video type."""
    evidence: list[str] = []
    if has_video_title_marker(track):
        evidence.append("title-marker")
    if has_video_thumbnail(track):
        evidence.append("wide-thumbnail")
    if not track.get("album"):
        evidence.append("missing-album")
    return evidence


def is_video_variant(track: Mapping[str, object]) -> bool:
    """Identify videos even when YouTube Music omits their videoType."""
    if track.get("videoType") in VIDEO_TYPES or has_video_title_marker(track):
        return True
    return has_video_thumbnail(track) and not track.get("album")
