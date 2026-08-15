"""Account-scoped library and playlist application layer."""

from .commands import (
    MAX_MUTATION_BATCH,
    parse_add_playlist_items,
    parse_create_playlist,
    parse_edit_playlist,
    parse_rating,
    parse_remove_playlist_items,
    parse_song_metadata,
    parse_song_rating_payload,
    required_id,
)
from .context import ActiveMusicProfile, SessionActiveMusicProfile
from .errors import (
    AccountConflictError,
    AccountError,
    AccountInternalError,
    AccountProviderUnavailableError,
    AccountValidationError,
    AuthenticationRequiredError,
    LocalOperationNotSupportedError,
)
from .repositories import LocalMusicRepository
from .services import (
    ArtistSubscriptionService,
    LibraryService,
    LikedSongsService,
    ListeningHistoryService,
    PlaylistService,
    SongRatingService,
    liked_song_json,
    local_liked_song_json,
)

__all__ = [
    "MAX_MUTATION_BATCH",
    "AccountConflictError",
    "AccountError",
    "AccountInternalError",
    "AccountProviderUnavailableError",
    "AccountValidationError",
    "ActiveMusicProfile",
    "ArtistSubscriptionService",
    "AuthenticationRequiredError",
    "LibraryService",
    "LikedSongsService",
    "ListeningHistoryService",
    "LocalMusicRepository",
    "LocalOperationNotSupportedError",
    "PlaylistService",
    "SessionActiveMusicProfile",
    "SongRatingService",
    "liked_song_json",
    "local_liked_song_json",
    "parse_add_playlist_items",
    "parse_create_playlist",
    "parse_edit_playlist",
    "parse_rating",
    "parse_remove_playlist_items",
    "parse_song_metadata",
    "parse_song_rating_payload",
    "required_id",
]
