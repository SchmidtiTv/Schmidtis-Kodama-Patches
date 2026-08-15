"""Normalize untyped ytmusicapi account payloads."""

from collections.abc import Mapping, Sequence

from src.lib.music.video_variants import has_video_thumbnail, video_evidence
from src.lib.music.youtube_data import YoutubeResponseMapper

from ..models import CatalogArtistReference, LikedSong, PlaylistTrack


def mapping_items(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def text(value: object) -> str:
    return value if isinstance(value, str) else ""


def artists(value: object) -> tuple[CatalogArtistReference, ...]:
    raw_artists = YoutubeResponseMapper.drop_type_label_artist(value)
    return tuple(
        CatalogArtistReference(
            name=text(raw.get("name")),
            browse_id=text(raw.get("id")) or text(raw.get("browseId")),
        )
        for raw in raw_artists
        if text(raw.get("name"))
    )


def liked_song(raw: Mapping[str, object]) -> LikedSong | None:
    video_id = text(raw.get("videoId"))
    if not video_id:
        return None
    normalized_artists = artists(raw.get("artists"))
    evidence = video_evidence(raw)
    album = raw.get("album")
    album_mapping = album if isinstance(album, Mapping) else {}
    return LikedSong(
        video_id=video_id,
        title=text(raw.get("title")),
        artists=", ".join(artist.name for artist in normalized_artists),
        artist_browse_id=normalized_artists[0].browse_id if normalized_artists else "",
        artist_links=normalized_artists,
        album=text(album_mapping.get("name")),
        album_browse_id=text(album_mapping.get("id")),
        duration=text(raw.get("duration")),
        thumbnail=YoutubeResponseMapper.select_thumbnail(raw.get("thumbnails")),
        is_explicit=raw.get("isExplicit") is True,
        video_type=text(raw.get("videoType")),
        is_detected_video=bool(evidence),
    )


def playlist_track(raw: Mapping[str, object]) -> PlaylistTrack | None:
    video_id = text(raw.get("videoId"))
    if not video_id:
        return None
    raw_thumbnails = mapping_items(raw.get("thumbnails") or raw.get("thumbnail"))
    normalized = dict(raw)
    normalized["thumbnails"] = raw_thumbnails
    evidence = video_evidence(normalized)
    album = raw.get("album")
    album_mapping = album if isinstance(album, Mapping) else {}
    dimensions = tuple(
        f"{width}x{height}"
        for thumbnail in raw_thumbnails
        if isinstance((width := thumbnail.get("width")), int)
        and isinstance((height := thumbnail.get("height")), int)
    )
    return PlaylistTrack(
        video_id=video_id,
        set_video_id=text(raw.get("setVideoId")),
        title=text(raw.get("title")),
        artists=artists(raw.get("artists")),
        album=text(album_mapping.get("name")),
        album_browse_id=text(album_mapping.get("id")),
        duration=text(raw.get("duration")) or text(raw.get("length")),
        thumbnails=tuple(text(thumbnail.get("url")) for thumbnail in raw_thumbnails),
        is_explicit=raw.get("isExplicit") is True,
        video_type=text(raw.get("videoType")),
        is_detected_video=bool(evidence),
        video_evidence=tuple(evidence),
        thumbnail_dimensions=dimensions,
        has_video_thumbnail=has_video_thumbnail(normalized),
    )


def track_payload(track: PlaylistTrack) -> dict[str, object]:
    """Build an adapter-owned ytmusicapi-shaped value for audio resolution."""
    return {
        "videoId": track.video_id,
        "setVideoId": track.set_video_id,
        "title": track.title,
        "artists": [{"name": artist.name, "id": artist.browse_id} for artist in track.artists],
        "album": {"name": track.album, "id": track.album_browse_id},
        "duration": track.duration,
        "thumbnails": [{"url": url} for url in track.thumbnails],
        "isExplicit": track.is_explicit,
        "videoType": track.video_type,
        "isDetectedVideo": track.is_detected_video,
    }
