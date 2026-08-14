"""Response parsing for mood and genre discovery routes."""

from typing import cast

from src.lib import YoutubeResponseMapper


def _parse_two_row_item(renderer: dict[str, object]) -> dict[str, object] | None:
    """Parse a musicTwoRowItemRenderer (used on mood/genre category pages) into
    our generic item shape. Handles playlists, albums, artists and songs.
    """
    title = ""
    try:
        title_data = cast("dict[str, object]", renderer["title"])
        runs = cast("list[dict[str, object]]", title_data["runs"])
        title = str(runs[0]["text"])
    except (KeyError, IndexError, TypeError):
        pass
    subtitle = ""
    try:
        subtitle_data = cast("dict[str, object]", renderer.get("subtitle", {}))
        subtitle = "".join(
            str(run.get("text", ""))
            for run in cast("list[dict[str, object]]", subtitle_data.get("runs", []))
        )
    except (KeyError, TypeError):
        pass
    thumb = None
    try:
        thumbnail_renderer = cast("dict[str, object]", renderer["thumbnailRenderer"])
        music_thumbnail = cast("dict[str, object]", thumbnail_renderer["musicThumbnailRenderer"])
        thumbnail = cast("dict[str, object]", music_thumbnail["thumbnail"])
        thumbs = cast("list[dict[str, object]]", thumbnail["thumbnails"])
        thumb = YoutubeResponseMapper.select_thumbnail(thumbs)
    except (KeyError, TypeError):
        pass
    nav = cast("dict[str, object]", renderer.get("navigationEndpoint", {}) or {})
    if "watchPlaylistEndpoint" in nav:
        endpoint = cast("dict[str, object]", nav["watchPlaylistEndpoint"])
        return {
            "type": "playlist",
            "playlistId": endpoint.get("playlistId", ""),
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if "watchEndpoint" in nav:
        we = cast("dict[str, object]", nav["watchEndpoint"])
        return {
            "type": "song",
            "videoId": we.get("videoId", ""),
            "playlistId": we.get("playlistId", ""),
            "title": title,
            "artists": subtitle,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    browse_id = str(
        cast("dict[str, object]", nav.get("browseEndpoint", {}) or {}).get("browseId", "")
    )
    if browse_id.startswith("VL"):
        return {
            "type": "playlist",
            "playlistId": browse_id[2:],
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if browse_id.startswith("MPRE"):
        return {
            "type": "album",
            "browseId": browse_id,
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if browse_id.startswith("UC"):
        return {
            "type": "artist",
            "browseId": browse_id,
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if browse_id:
        return {
            "type": "playlist",
            "playlistId": browse_id,
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    return None
