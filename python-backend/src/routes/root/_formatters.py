"""Response formatting shared by top-level music discovery routes."""

from typing import cast

from src.lib import YoutubeResponseMapper


def song_result(track: dict[str, object]) -> dict[str, object]:
    artists = cast(
        "list[dict[str, str]]",
        YoutubeResponseMapper.drop_type_label_artist(
            cast("list[dict[str, str]]", track.get("artists", []))
        ),
    )
    album = cast("dict[str, str]", track.get("album") or {})
    return {
        "type": "song",
        "videoId": track.get("videoId", ""),
        "title": track.get("title", ""),
        "artists": ", ".join(artist["name"] for artist in artists),
        "artistBrowseId": (artists[0].get("id") or "") if artists else "",
        "artistLinks": YoutubeResponseMapper.build_artist_links(artists),
        "album": album.get("name", ""),
        "albumBrowseId": album.get("id") or "",
        "duration": track.get("duration", ""),
        "thumbnail": YoutubeResponseMapper.select_thumbnail(
            cast("list[dict[str, object]]", track.get("thumbnails", []))
        ),
        "isExplicit": bool(track.get("isExplicit", False)),
    }


def is_podcast_section(title: str) -> bool:
    """Identify home-feed sections which contain shows and podcast episodes."""
    normalized_title = title.lower()
    return (
        "podcast" in normalized_title or "episode" in normalized_title or "show" in normalized_title
    )


def is_signed_out_ytmusic_error(error: Exception) -> bool:
    """Recognize ytmusicapi's parser error for an expired YouTube session."""
    message = str(error)
    return (
        "twoColumnBrowseResultsRenderer" in message
        or "singleColumnBrowseResultsRenderer" in message
    )
