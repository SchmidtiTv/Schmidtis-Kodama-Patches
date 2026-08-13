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
        {
            "album",
            "artist",
            "ep",
            "episode",
            "playlist",
            "podcast",
            "profile",
            "single",
            "song",
            "station",
            "video",
        }
    )

    @staticmethod
    def _mapping_sequence(value: object) -> list[Mapping[str, object]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return []
        return [item for item in value if isinstance(item, Mapping)]

    @staticmethod
    def drop_type_label_artist(
        artist_list: object,
    ) -> list[Mapping[str, object]]:
        """Return artists without a leading result-type label parsed as an artist."""
        artists = YoutubeResponseMapper._mapping_sequence(artist_list)
        if not artists or artists[0].get("id") or artists[0].get("browseId"):
            return artists
        name = artists[0].get("name")
        if isinstance(name, str) and name.casefold() in YoutubeResponseMapper.RESULT_TYPE_LABELS:
            return artists[1:]
        return artists

    @staticmethod
    # Old server.py: _artist_links
    def build_artist_links(
        artist_list: object,
    ) -> list[dict[str, object]]:
        """Return artists with a name and browse identifier."""
        return [
            {
                "name": artist.get("name", ""),
                "browseId": artist.get("id") or artist.get("browseId") or "",
            }
            for artist in YoutubeResponseMapper._mapping_sequence(artist_list)
            if artist.get("name")
        ]

    @staticmethod
    # Old server.py: _pick_thumb
    def select_thumbnail(thumbs: object, min_size: int = 226) -> str:
        """Pick the smallest thumbnail at least ``min_size`` pixels wide."""
        thumbnails = YoutubeResponseMapper._mapping_sequence(thumbs)
        if not thumbnails:
            return ""
        candidates = [
            thumb
            for thumb in thumbnails
            if isinstance(thumb.get("width"), int) and cast("int", thumb["width"]) >= min_size
        ]
        chosen = (
            min(candidates, key=lambda thumb: cast("int", thumb["width"]))
            if candidates
            else thumbnails[0]
        )
        url = chosen.get("url", "")
        return url if isinstance(url, str) else ""

    @staticmethod
    # Old server.py: _upscale_thumbnail_url
    def upscale_thumbnail_url(url: str) -> str:
        """Return a higher-resolution variant of a YouTube or Google image URL."""
        url = re.sub(r"=w\d+-h\d+[^&?#\s]*", "=w0-h0", url)
        return re.sub(r"/(mq|sd)?default\.jpg", "/hqdefault.jpg", url)
