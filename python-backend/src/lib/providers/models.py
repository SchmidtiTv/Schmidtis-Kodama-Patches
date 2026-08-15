"""Provider-neutral values returned across capability boundaries."""

from dataclasses import dataclass
from enum import StrEnum

MAX_PLAYLIST_MUTATION_ITEMS = 500


class CatalogSearchFilter(StrEnum):
    """Search categories currently accepted by Kodama's public API."""

    ALL = "all"
    ALBUMS = "albums"
    ARTISTS = "artists"
    COMMUNITY_PLAYLISTS = "community_playlists"
    EPISODES = "episodes"
    FEATURED_PLAYLISTS = "featured_playlists"
    PLAYLISTS = "playlists"
    PODCASTS = "podcasts"
    PROFILES = "profiles"
    SONGS = "songs"
    VIDEOS = "videos"


@dataclass(frozen=True, slots=True)
class CatalogSearchQuery:
    """Validated catalog search input."""

    text: str
    filter: CatalogSearchFilter
    limit: int = 20


@dataclass(frozen=True, slots=True)
class CatalogArtistReference:
    """An artist name and its optional provider browse identity."""

    name: str
    browse_id: str = ""


@dataclass(frozen=True, slots=True)
class CatalogSong:
    """A song returned by a provider catalog search."""

    video_id: str
    title: str
    artists: tuple[CatalogArtistReference, ...]
    album: str = ""
    album_browse_id: str = ""
    duration: str = ""
    thumbnail: str = ""
    is_explicit: bool = False


@dataclass(frozen=True, slots=True)
class CatalogArtist:
    """An artist returned by a catalog search."""

    browse_id: str
    title: str
    subscribers: str
    thumbnail: str


@dataclass(frozen=True, slots=True)
class CatalogAlbumSummary:
    """An album returned by a catalog search."""

    browse_id: str
    title: str
    artists: tuple[CatalogArtistReference, ...]
    year: str
    thumbnail: str


@dataclass(frozen=True, slots=True)
class CatalogPlaylist:
    """A playlist returned by a catalog search."""

    playlist_id: str
    browse_id: str
    title: str
    author: str
    thumbnail: str


type CatalogSearchResult = CatalogSong | CatalogArtist | CatalogAlbumSummary | CatalogPlaylist


@dataclass(frozen=True, slots=True)
class CatalogTrack:
    """A normalized playable album track."""

    video_id: str
    title: str
    artists: tuple[CatalogArtistReference, ...]
    duration: str
    is_explicit: bool


@dataclass(frozen=True, slots=True)
class CatalogAlbum:
    """A normalized catalog album with playable tracks."""

    browse_id: str
    title: str
    artists: tuple[CatalogArtistReference, ...]
    year: str
    thumbnail: str
    tracks: tuple[CatalogTrack, ...]


@dataclass(frozen=True, slots=True)
class LibrarySongState:
    """The normalized result of changing a song's library state."""

    video_id: str
    liked: bool


@dataclass(frozen=True, slots=True)
class PlaylistReference:
    """The stable identity and display name of a provider playlist."""

    playlist_id: str
    title: str


@dataclass(frozen=True, slots=True)
class SongStatistics:
    """Provider-neutral engagement counts for a song."""

    views: int | None
    likes: int | None
    dislikes: int | None


@dataclass(frozen=True, slots=True)
class SongCredits:
    """Normalized public song description used by the credits page."""

    description: str


class SongRating(StrEnum):
    """Ratings accepted by YouTube Music and Kodama's local library."""

    LIKE = "LIKE"
    DISLIKE = "DISLIKE"
    INDIFFERENT = "INDIFFERENT"


class PlaylistPrivacy(StrEnum):
    """Portable playlist visibility values."""

    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"
    UNLISTED = "UNLISTED"


@dataclass(frozen=True, slots=True)
class LibraryAlbum:
    browse_id: str
    title: str
    artists: str
    year: str
    thumbnail: str


@dataclass(frozen=True, slots=True)
class LibraryArtist:
    browse_id: str
    artist: str
    songs: str
    thumbnail: str


@dataclass(frozen=True, slots=True)
class LibraryPlaylist:
    playlist_id: str
    title: str
    count: str
    thumbnail: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class LikedSong:
    video_id: str
    title: str
    artists: str
    artist_browse_id: str
    artist_links: tuple[CatalogArtistReference, ...]
    album: str
    album_browse_id: str
    duration: str
    thumbnail: str
    is_explicit: bool
    video_type: str = ""
    is_detected_video: bool = False


@dataclass(frozen=True, slots=True)
class LikedSongsQuery:
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if self.offset < 0 or not 1 <= self.limit <= 100:
            raise ValueError("offset must be non-negative and limit must be between 1 and 100")


@dataclass(frozen=True, slots=True)
class LikedSongsPage:
    tracks: tuple[LikedSong, ...]
    total: int | None = None
    offset: int | None = None
    has_more: bool | None = None


@dataclass(frozen=True, slots=True)
class PlaylistTrackMetadata:
    video_id: str
    title: str = ""
    artists: str = ""
    album: str = ""
    thumbnail: str = ""
    duration: str = ""

    def __post_init__(self) -> None:
        _validate_required_id(self.video_id, "track video ID")


@dataclass(frozen=True, slots=True)
class PlaylistItemReference:
    video_id: str
    set_video_id: str = ""

    def __post_init__(self) -> None:
        _validate_required_id(self.video_id, "playlist item video ID")
        if not isinstance(self.set_video_id, str):
            raise ValueError("playlist item set video ID must be a string")


@dataclass(frozen=True, slots=True)
class PlaylistTrack:
    video_id: str
    set_video_id: str
    title: str
    artists: tuple[CatalogArtistReference, ...]
    album: str
    album_browse_id: str
    duration: str
    thumbnails: tuple[str, ...]
    is_explicit: bool = False
    video_type: str = ""
    is_detected_video: bool = False
    video_evidence: tuple[str, ...] = ()
    thumbnail_dimensions: tuple[str, ...] = ()
    has_video_thumbnail: bool = False


@dataclass(frozen=True, slots=True)
class PlaylistDetails:
    title: str
    thumbnail: str
    tracks: tuple[PlaylistTrack, ...]


@dataclass(frozen=True, slots=True)
class CreatedPlaylist:
    playlist_id: str


@dataclass(frozen=True, slots=True)
class PlaylistRadio:
    tracks: tuple[PlaylistTrack, ...]


@dataclass(frozen=True, slots=True)
class CreatePlaylist:
    title: str
    description: str
    privacy: PlaylistPrivacy
    video_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("playlist title must not be empty")
        if not isinstance(self.description, str):
            raise ValueError("playlist description must be a string")
        if not isinstance(self.privacy, PlaylistPrivacy):
            raise ValueError("unsupported playlist privacy")
        _validate_video_ids(self.video_ids, allow_empty=True)


@dataclass(frozen=True, slots=True)
class AddPlaylistItems:
    playlist_id: str
    video_ids: tuple[str, ...]
    tracks: tuple[PlaylistTrackMetadata, ...]

    def __post_init__(self) -> None:
        _validate_required_id(self.playlist_id, "playlist ID")
        _validate_video_ids(self.video_ids, allow_empty=False)
        if not isinstance(self.tracks, tuple) or not all(
            isinstance(track, PlaylistTrackMetadata) for track in self.tracks
        ):
            raise ValueError("playlist tracks must be a tuple of track metadata")
        track_ids = tuple(track.video_id for track in self.tracks)
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("duplicate track video ID")


@dataclass(frozen=True, slots=True)
class RemovePlaylistItems:
    playlist_id: str
    items: tuple[PlaylistItemReference, ...]

    def __post_init__(self) -> None:
        _validate_required_id(self.playlist_id, "playlist ID")
        if not isinstance(self.items, tuple) or not self.items:
            raise ValueError("playlist items must be a non-empty tuple")
        if len(self.items) > MAX_PLAYLIST_MUTATION_ITEMS or not all(
            isinstance(item, PlaylistItemReference) for item in self.items
        ):
            raise ValueError("invalid playlist item collection")
        keys = tuple((item.video_id, item.set_video_id) for item in self.items)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate playlist item reference")


@dataclass(frozen=True, slots=True)
class EditPlaylist:
    playlist_id: str
    title: str | None
    description: str | None
    privacy: PlaylistPrivacy | None

    def __post_init__(self) -> None:
        _validate_required_id(self.playlist_id, "playlist ID")
        if self.title is not None and (not isinstance(self.title, str) or not self.title.strip()):
            raise ValueError("playlist title must not be empty")
        if self.description is not None and not isinstance(self.description, str):
            raise ValueError("playlist description must be a string")
        if self.privacy is not None and not isinstance(self.privacy, PlaylistPrivacy):
            raise ValueError("unsupported playlist privacy")


def _validate_required_id(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")


def _validate_video_ids(video_ids: object, *, allow_empty: bool) -> None:
    if not isinstance(video_ids, tuple):
        raise ValueError("video IDs must be a tuple")
    if not video_ids and not allow_empty:
        raise ValueError("video IDs must not be empty")
    if len(video_ids) > MAX_PLAYLIST_MUTATION_ITEMS:
        raise ValueError("playlist mutation batch is too large")
    for video_id in video_ids:
        _validate_required_id(video_id, "video ID")
    if len(video_ids) != len(set(video_ids)):
        raise ValueError("duplicate video ID")
