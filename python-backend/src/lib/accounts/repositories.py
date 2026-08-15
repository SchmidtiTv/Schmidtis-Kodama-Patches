"""Repositories for Kodama's persisted local-profile music state."""

import time
import uuid

from src.lib.profiles.profile import Profile
from src.lib.providers.models import (
    AddPlaylistItems,
    CatalogArtistReference,
    CreatedPlaylist,
    CreatePlaylist,
    EditPlaylist,
    LibraryPlaylist,
    LikedSong,
    PlaylistDetails,
    PlaylistTrack,
    RemovePlaylistItems,
    SongRating,
)

from .errors import AccountConflictError


class LocalMusicRepository:
    """Own all SQLite access for local libraries and playlists."""

    def __init__(self, profiles: Profile) -> None:
        self._profiles = profiles

    def library_playlists(self, profile_name: str) -> tuple[LibraryPlaylist, ...]:
        with self._profiles.local_database(profile_name) as database:
            rows = database.execute(
                "SELECT playlist_id, title, description, "
                "(SELECT COUNT(*) FROM playlist_tracks "
                "WHERE playlist_id=p.playlist_id) "
                "FROM playlists p ORDER BY updated_at DESC"
            ).fetchall()
        return tuple(
            LibraryPlaylist(
                playlist_id=str(row[0]),
                title=str(row[1] or ""),
                description=str(row[2] or ""),
                count=str(row[3]),
                thumbnail="",
            )
            for row in rows
        )

    def liked_songs(self, profile_name: str) -> tuple[LikedSong, ...]:
        with self._profiles.local_database(profile_name) as database:
            rows = database.execute(
                "SELECT video_id, title, artists, album, thumbnail, duration "
                "FROM liked_songs ORDER BY liked_at DESC"
            ).fetchall()
        return tuple(self._liked_song(row) for row in rows)

    def liked_song_ids(self, profile_name: str) -> frozenset[str]:
        with self._profiles.local_database(profile_name) as database:
            rows = database.execute("SELECT video_id FROM liked_songs").fetchall()
        return frozenset(str(row[0]) for row in rows)

    def rate_song(
        self,
        profile_name: str,
        video_id: str,
        rating: SongRating,
        metadata: dict[str, str],
    ) -> None:
        with self._profiles.local_database(profile_name) as database:
            if rating is SongRating.LIKE:
                database.execute(
                    "INSERT OR REPLACE INTO liked_songs "
                    "(video_id, title, artists, album, thumbnail, duration, liked_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        video_id,
                        metadata["title"],
                        metadata["artists"],
                        metadata["album"],
                        metadata["thumbnail"],
                        metadata["duration"],
                        int(time.time()),
                    ),
                )
            else:
                database.execute("DELETE FROM liked_songs WHERE video_id=?", (video_id,))
            database.commit()

    def get_playlist(self, profile_name: str, playlist_id: str) -> PlaylistDetails:
        with self._profiles.local_database(profile_name) as database:
            if playlist_id == "LM":
                rows = database.execute(
                    "SELECT video_id, title, artists, album, thumbnail, duration "
                    "FROM liked_songs ORDER BY liked_at DESC"
                ).fetchall()
                return PlaylistDetails(
                    title="Gelikte Songs",
                    thumbnail="",
                    tracks=tuple(self._liked_playlist_track(row) for row in rows),
                )
            playlist = database.execute(
                "SELECT title FROM playlists WHERE playlist_id=?", (playlist_id,)
            ).fetchone()
            if playlist is None:
                raise AccountConflictError("Playlist does not exist")
            rows = database.execute(
                "SELECT video_id, set_video_id, title, artists, album, thumbnail, duration "
                "FROM playlist_tracks WHERE playlist_id=? ORDER BY position ASC",
                (playlist_id,),
            ).fetchall()
        return PlaylistDetails(
            title=str(playlist[0]),
            thumbnail="",
            tracks=tuple(self._playlist_track(row) for row in rows),
        )

    def create_playlist(self, profile_name: str, command: CreatePlaylist) -> CreatedPlaylist:
        playlist_id = str(uuid.uuid4())
        now = int(time.time())
        with self._profiles.local_database(profile_name) as database:
            database.execute(
                "INSERT INTO playlists "
                "(playlist_id, title, description, privacy, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    playlist_id,
                    command.title,
                    command.description,
                    command.privacy.value,
                    now,
                    now,
                ),
            )
            database.commit()
        if command.video_ids:
            self.add_playlist_items(
                profile_name,
                AddPlaylistItems(playlist_id, command.video_ids, ()),
            )
        return CreatedPlaylist(playlist_id)

    def edit_playlist(self, profile_name: str, command: EditPlaylist) -> None:
        with self._profiles.local_database(profile_name) as database:
            if command.title is not None:
                database.execute(
                    "UPDATE playlists SET title=?, updated_at=? WHERE playlist_id=?",
                    (command.title, int(time.time()), command.playlist_id),
                )
            if command.description is not None:
                database.execute(
                    "UPDATE playlists SET description=? WHERE playlist_id=?",
                    (command.description, command.playlist_id),
                )
            if command.privacy is not None:
                database.execute(
                    "UPDATE playlists SET privacy=? WHERE playlist_id=?",
                    (command.privacy.value, command.playlist_id),
                )
            database.commit()

    def delete_playlist(self, profile_name: str, playlist_id: str) -> None:
        with self._profiles.local_database(profile_name) as database:
            database.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
            database.execute("DELETE FROM playlists WHERE playlist_id=?", (playlist_id,))
            database.commit()

    def add_playlist_items(self, profile_name: str, command: AddPlaylistItems) -> None:
        metadata = {track.video_id: track for track in command.tracks}
        now = int(time.time())
        with self._profiles.local_database(profile_name) as database:
            row = database.execute(
                "SELECT COALESCE(MAX(position),0) FROM playlist_tracks WHERE playlist_id=?",
                (command.playlist_id,),
            ).fetchone()
            max_position = int(row[0]) if row else 0
            for index, video_id in enumerate(command.video_ids):
                track = metadata.get(video_id)
                database.execute(
                    "INSERT INTO playlist_tracks "
                    "(playlist_id, video_id, title, artists, album, thumbnail, duration, "
                    "set_video_id, position, added_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        command.playlist_id,
                        video_id,
                        track.title if track else "",
                        track.artists if track else "",
                        track.album if track else "",
                        track.thumbnail if track else "",
                        track.duration if track else "",
                        str(uuid.uuid4()),
                        max_position + index + 1,
                        now,
                    ),
                )
            database.execute(
                "UPDATE playlists SET updated_at=? WHERE playlist_id=?",
                (now, command.playlist_id),
            )
            database.commit()

    def remove_playlist_items(self, profile_name: str, command: RemovePlaylistItems) -> None:
        with self._profiles.local_database(profile_name) as database:
            for item in command.items:
                if item.set_video_id:
                    database.execute(
                        "DELETE FROM playlist_tracks " "WHERE playlist_id=? AND set_video_id=?",
                        (command.playlist_id, item.set_video_id),
                    )
                else:
                    database.execute(
                        "DELETE FROM playlist_tracks WHERE playlist_id=? AND video_id=?",
                        (command.playlist_id, item.video_id),
                    )
            database.execute(
                "UPDATE playlists SET updated_at=? WHERE playlist_id=?",
                (int(time.time()), command.playlist_id),
            )
            database.commit()

    @staticmethod
    def _liked_song(row: tuple[object, ...]) -> LikedSong:
        artists = str(row[2] or "")
        return LikedSong(
            video_id=str(row[0]),
            title=str(row[1] or ""),
            artists=artists,
            artist_browse_id="",
            artist_links=(),
            album=str(row[3] or ""),
            album_browse_id="",
            thumbnail=str(row[4] or ""),
            duration=str(row[5] or ""),
            is_explicit=False,
        )

    @staticmethod
    def _liked_playlist_track(row: tuple[object, ...]) -> PlaylistTrack:
        return PlaylistTrack(
            video_id=str(row[0]),
            set_video_id=str(row[0]),
            title=str(row[1] or ""),
            artists=(CatalogArtistReference(str(row[2] or "")),) if row[2] else (),
            album=str(row[3] or ""),
            album_browse_id="",
            thumbnails=(str(row[4]),) if row[4] else (),
            duration=str(row[5] or ""),
        )

    @staticmethod
    def _playlist_track(row: tuple[object, ...]) -> PlaylistTrack:
        return PlaylistTrack(
            video_id=str(row[0]),
            set_video_id=str(row[1] or ""),
            title=str(row[2] or ""),
            artists=(CatalogArtistReference(str(row[3] or "")),) if row[3] else (),
            album=str(row[4] or ""),
            album_browse_id="",
            thumbnails=(str(row[5]),) if row[5] else (),
            duration=str(row[6] or ""),
        )
