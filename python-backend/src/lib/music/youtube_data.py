"""Mapping helpers for YouTube Music response payloads."""

import re
from collections.abc import Mapping, Sequence
from typing import cast


class YoutubeResponseMapper:
    """Normalizes artists and thumbnails from YouTube response payloads."""

    # YouTube prefixes a search row's byline with the row type ("Song • 5:00").
    # ytmusicapi normally strips it, but not when the row omits the artist -- as
    # the shelf below a "Top result" artist card does -- and then parses the
    # label itself as an artist without an identifier.
    RESULT_TYPE_LABELS = frozenset(
        {"album", "artist", "ep", "episode", "playlist", "podcast", "profile", "single", "song", "station", "video"}
    )

    @staticmethod
    def drop_type_label_artist(artist_list: Sequence[Mapping[str, object]] | None) -> list[Mapping[str, object]]:
        """Return artists without a leading result-type label parsed as an artist."""
        artists = list(artist_list or [])
        if not artists or artists[0].get("id") or artists[0].get("browseId"):
            return artists
        name = artists[0].get("name")
        if isinstance(name, str) and name.casefold() in YoutubeResponseMapper.RESULT_TYPE_LABELS:
            return artists[1:]
        return artists

    @staticmethod
    # Old server.py: _artist_links
    def build_artist_links(artist_list: Sequence[Mapping[str, object]] | None) -> list[dict[str, object]]:
        """Return artists with a name and browse identifier."""
        return [
            {"name": artist.get("name", ""), "browseId": artist.get("id") or artist.get("browseId") or ""}
            for artist in (artist_list or [])
            if artist.get("name")
        ]

    @staticmethod
    # Old server.py: _pick_thumb
    def select_thumbnail(thumbs: Sequence[Mapping[str, object]] | None, min_size: int = 226) -> str:
        """Pick the smallest thumbnail at least ``min_size`` pixels wide."""
        if not thumbs:
            return ""
        valid_thumbs = [thumb for thumb in thumbs if isinstance(thumb, Mapping)]
        if not valid_thumbs:
            return ""
        candidates = [thumb for thumb in valid_thumbs if isinstance(thumb.get("width"), int) and cast(int, thumb["width"]) >= min_size]
        chosen = (
            min(candidates, key=lambda thumb: cast(int, thumb["width"]))
            if candidates
            else max(valid_thumbs, key=lambda thumb: int(thumb.get("width") or 0))
        )
        url = chosen.get("url", "")
        return url if isinstance(url, str) else ""

    @staticmethod
    # Old server.py: _upscale_thumbnail_url
    def upscale_thumbnail_url(url: str) -> str:
        """Return a higher-resolution variant of a YouTube or Google image URL."""
        url = re.sub(r"=w\d+-h\d+[^&?#\s]*", "=w0-h0", url)
        return re.sub(r"/(mq|sd)?default\.jpg", "/hqdefault.jpg", url)
