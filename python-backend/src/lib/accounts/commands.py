"""Parsing and validation for immutable account mutation commands."""

from collections.abc import Mapping

from src.lib.providers.models import (
    MAX_PLAYLIST_MUTATION_ITEMS,
    AddPlaylistItems,
    CreatePlaylist,
    EditPlaylist,
    PlaylistItemReference,
    PlaylistPrivacy,
    PlaylistTrackMetadata,
    RemovePlaylistItems,
    SongRating,
)

from .errors import AccountValidationError

MAX_MUTATION_BATCH = MAX_PLAYLIST_MUTATION_ITEMS


def required_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AccountValidationError(f"{field} required")
    return value.strip()


def parse_rating(value: object) -> SongRating:
    try:
        return SongRating(value)
    except (TypeError, ValueError):
        raise AccountValidationError("Unsupported rating value") from None


def parse_song_metadata(data: object) -> dict[str, str]:
    payload = _mapping(data)
    return {
        field: _optional_string(payload.get(field), field)
        for field in ("title", "artists", "album", "thumbnail", "duration")
    }


def parse_song_rating_payload(data: object) -> tuple[SongRating, dict[str, str]]:
    payload = _mapping(data)
    return parse_rating(payload.get("rating", SongRating.LIKE.value)), parse_song_metadata(payload)


def parse_create_playlist(data: object) -> CreatePlaylist:
    payload = _mapping(data)
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise AccountValidationError("Title is required")
    description = payload.get("description", "")
    if not isinstance(description, str):
        raise AccountValidationError("description must be a string")
    privacy = _privacy(payload.get("privacyStatus", PlaylistPrivacy.PRIVATE.value))
    video_ids = _video_ids(payload.get("videoIds", []), allow_empty=True)
    return CreatePlaylist(title.strip(), description, privacy, video_ids)


def parse_add_playlist_items(playlist_id: object, data: object) -> AddPlaylistItems:
    normalized_playlist_id = required_id(playlist_id, "playlistId")
    payload = _mapping(data)
    video_ids = _video_ids(payload.get("videoIds"), allow_empty=False)
    raw_tracks = payload.get("tracks", [])
    if not isinstance(raw_tracks, list):
        raise AccountValidationError("tracks must be a list")
    tracks: list[PlaylistTrackMetadata] = []
    seen_tracks: set[str] = set()
    for raw in raw_tracks:
        if not isinstance(raw, Mapping):
            raise AccountValidationError("Malformed playlist track metadata")
        video_id = required_id(raw.get("videoId"), "track videoId")
        if video_id in seen_tracks:
            raise AccountValidationError("Duplicate track videoId")
        seen_tracks.add(video_id)
        tracks.append(
            PlaylistTrackMetadata(
                video_id=video_id,
                title=_optional_string(raw.get("title"), "title"),
                artists=_optional_string(raw.get("artists"), "artists"),
                album=_optional_string(raw.get("album"), "album"),
                thumbnail=_optional_string(raw.get("thumbnail"), "thumbnail"),
                duration=_optional_string(raw.get("duration"), "duration"),
            )
        )
    if seen_tracks - set(video_ids):
        raise AccountValidationError("Track metadata must match videoIds")
    return AddPlaylistItems(normalized_playlist_id, video_ids, tuple(tracks))


def parse_remove_playlist_items(playlist_id: object, data: object) -> RemovePlaylistItems:
    normalized_playlist_id = required_id(playlist_id, "playlistId")
    payload = _mapping(data)
    raw_items = payload.get("videos")
    if not isinstance(raw_items, list) or not raw_items:
        raise AccountValidationError("videos required")
    if len(raw_items) > MAX_MUTATION_BATCH:
        raise AccountValidationError("Playlist mutation batch is too large")
    items: list[PlaylistItemReference] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            raise AccountValidationError("Malformed playlist item reference")
        video_id = required_id(raw.get("videoId"), "videoId")
        set_video_id = raw.get("setVideoId", "")
        if not isinstance(set_video_id, str):
            raise AccountValidationError("Malformed playlist item reference")
        key = (video_id, set_video_id.strip())
        if key in seen:
            raise AccountValidationError("Duplicate playlist item reference")
        seen.add(key)
        items.append(PlaylistItemReference(*key))
    return RemovePlaylistItems(normalized_playlist_id, tuple(items))


def parse_edit_playlist(playlist_id: object, data: object) -> EditPlaylist:
    normalized_playlist_id = required_id(playlist_id, "playlistId")
    payload = _mapping(data)
    title = payload.get("title")
    if title is not None:
        if not isinstance(title, str) or not title.strip():
            raise AccountValidationError("Playlist title must not be empty")
        title = title.strip()
    description = payload.get("description")
    if description is not None and not isinstance(description, str):
        raise AccountValidationError("description must be a string")
    raw_privacy = payload.get("privacyStatus")
    privacy = _privacy(raw_privacy) if raw_privacy is not None else None
    return EditPlaylist(normalized_playlist_id, title, description, privacy)


def _mapping(data: object) -> Mapping[str, object]:
    if not isinstance(data, Mapping):
        raise AccountValidationError("JSON object required")
    return data


def _privacy(value: object) -> PlaylistPrivacy:
    try:
        return PlaylistPrivacy(value)
    except (TypeError, ValueError):
        raise AccountValidationError("Unsupported playlist privacy value") from None


def _video_ids(value: object, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise AccountValidationError("videoIds must be a list")
    if not value and not allow_empty:
        raise AccountValidationError("videoIds required")
    if len(value) > MAX_MUTATION_BATCH:
        raise AccountValidationError("Playlist mutation batch is too large")
    result = tuple(required_id(item, "videoId") for item in value)
    if len(set(result)) != len(result):
        raise AccountValidationError("Duplicate videoId")
    return result


def _optional_string(value: object, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AccountValidationError(f"{field} must be a string")
    return value
