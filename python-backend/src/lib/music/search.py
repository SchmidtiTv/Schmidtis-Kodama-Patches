"""Application-facing catalog search orchestration and response formatting."""

from src.lib.providers.contracts import MusicCatalogProvider
from src.lib.providers.models import (
    CatalogAlbumSummary,
    CatalogArtist,
    CatalogArtistReference,
    CatalogPlaylist,
    CatalogSearchQuery,
    CatalogSong,
)


class SearchService:
    """Search a catalog and produce Kodama's stable frontend representation."""

    SUGGESTION_LIMIT = 6

    def __init__(self, catalog: MusicCatalogProvider) -> None:
        self._catalog = catalog

    def search(self, query: CatalogSearchQuery) -> dict[str, list[dict[str, object]]]:
        if not query.text:
            return {"results": []}
        return {"results": [self._result(item) for item in self._catalog.search(query)]}

    def suggestions(self, query: str) -> dict[str, list[str]]:
        normalized_query = query.strip()
        if len(normalized_query) < 2:
            return {"suggestions": []}

        suggestions: list[str] = []
        seen: set[str] = set()
        for title in self._catalog.suggestions(normalized_query, self.SUGGESTION_LIMIT):
            normalized_title = title.strip()
            match_key = normalized_title.casefold()
            if not normalized_title or match_key in seen:
                continue
            seen.add(match_key)
            suggestions.append(normalized_title)
        return {"suggestions": suggestions}

    @classmethod
    def _result(cls, item: object) -> dict[str, object]:
        if isinstance(item, CatalogSong):
            return {
                "type": "song",
                "videoId": item.video_id,
                "title": item.title,
                "artists": cls._artist_names(item.artists),
                "artistBrowseId": cls._first_artist_id(item.artists),
                "artistLinks": cls._artist_links(item.artists),
                "album": item.album,
                "albumBrowseId": item.album_browse_id,
                "duration": item.duration,
                "thumbnail": item.thumbnail,
                "isExplicit": item.is_explicit,
            }
        if isinstance(item, CatalogArtist):
            return {
                "type": "artist",
                "browseId": item.browse_id,
                "title": item.title,
                "subtitle": item.subscribers,
                "thumbnail": item.thumbnail,
            }
        if isinstance(item, CatalogAlbumSummary):
            return {
                "type": "album",
                "browseId": item.browse_id,
                "title": item.title,
                "artists": cls._artist_names(item.artists),
                "year": item.year,
                "thumbnail": item.thumbnail,
            }
        if isinstance(item, CatalogPlaylist):
            return {
                "type": "playlist",
                "playlistId": item.playlist_id,
                "browseId": item.browse_id,
                "title": item.title,
                "subtitle": item.author,
                "thumbnail": item.thumbnail,
            }
        raise TypeError(f"Unsupported catalog search result: {type(item).__name__}")

    @staticmethod
    def _artist_names(artists: tuple[CatalogArtistReference, ...]) -> str:
        return ", ".join(artist.name for artist in artists)

    @staticmethod
    def _first_artist_id(artists: tuple[CatalogArtistReference, ...]) -> str:
        return artists[0].browse_id if artists else ""

    @staticmethod
    def _artist_links(
        artists: tuple[CatalogArtistReference, ...],
    ) -> list[dict[str, str]]:
        return [
            {"name": artist.name, "browseId": artist.browse_id} for artist in artists if artist.name
        ]
