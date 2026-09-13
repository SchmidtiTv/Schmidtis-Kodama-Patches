"""Return the normalized YouTube Music home feed."""

from flask import jsonify

from src.lib import YoutubeResponseMapper
from src.lib.music.audio_versions import prefer_audio_versions
from src.type_defs import RouteResponse

from . import blueprint
from ._formatters import is_podcast_section, song_result
from ._services import metadata_cache, music_session


def is_video_thumbnail(item: dict[str, object]) -> bool:
    """Classify unresolved home-feed video thumbnails without localized metadata."""
    thumbnails = item.get("thumbnails", [])
    if not isinstance(thumbnails, list):
        return False
    return any(
        isinstance(thumbnail, dict) and "ytimg.com" in str(thumbnail.get("url", ""))
        for thumbnail in thumbnails
    )


def section_contents(section: dict[str, object]) -> list[dict[str, object]]:
    """Return only valid item records from an upstream home-feed section."""
    contents = section.get("contents", [])
    if not isinstance(contents, list):
        return []
    return [item for item in contents if isinstance(item, dict)]


def artist_names(item: dict[str, object]) -> str:
    """Format the optional upstream artist collection without trusting its shape."""
    artists = item.get("artists", [])
    if not isinstance(artists, list):
        return ""
    return ", ".join(
        name
        for artist in artists
        if isinstance(artist, dict)
        if isinstance(name := artist.get("name"), str)
    )


@blueprint.route("/home")
def get_home() -> RouteResponse:
    try:
        client = music_session().get_active_client()
        resolver = music_session().get_system_client()
        upstream_home = client.get_home(limit=15)
        home = (
            [section for section in upstream_home if isinstance(section, dict)]
            if isinstance(upstream_home, list)
            else []
        )
        contents_by_section = [section_contents(section) for section in home]

        # Resolve every section's video-variant songs to their audio counterparts in a single
        # pass over the whole feed, instead of once per section (each call spins up its own
        # thread pool): up to 15 sequential thread-pool bursts otherwise, on a cache-miss.
        section_raw_songs = [
            [
                item
                for item in contents
                if item.get("videoId") and not is_podcast_section(str(section.get("title") or ""))
            ]
            for section, contents in zip(home, contents_by_section, strict=True)
        ]
        combined_songs = [song for songs in section_raw_songs for song in songs]
        resolved_combined = iter(
            prefer_audio_versions(resolver, None, combined_songs, metadata_cache())
        )
        section_resolved_songs = [
            [next(resolved_combined) for _ in songs] for songs in section_raw_songs
        ]

        sections = []
        for section, contents, resolved_songs_list in zip(
            home, contents_by_section, section_resolved_songs, strict=True
        ):
            raw_title = section.get("title", "")
            title = raw_title if isinstance(raw_title, str) else ""
            is_podcast = is_podcast_section(title)
            items = []
            resolved_songs = iter(resolved_songs_list)
            for item in contents:
                if item.get("videoId") and not is_podcast:
                    resolved_song = next(resolved_songs)
                    song = song_result(resolved_song)
                    song["isVideo"] = resolved_song.get("videoId") == item.get(
                        "videoId"
                    ) and is_video_thumbnail(item)
                    items.append(song)
                elif item.get("videoId"):
                    items.append(
                        {
                            "type": "podcast_episode",
                            "videoId": item.get("videoId", ""),
                            "browseId": item.get("browseId", ""),
                            "title": item.get("title", ""),
                            "subtitle": item.get("description", "") or item.get("date", ""),
                            "thumbnail": YoutubeResponseMapper.select_thumbnail(
                                item.get("thumbnails", [])
                            ),
                        }
                    )
                elif item.get("playlistId"):
                    items.append(
                        {
                            "type": "podcast" if is_podcast else "playlist",
                            "playlistId": item.get("playlistId", ""),
                            "title": item.get("title", ""),
                            "subtitle": item.get("description", "") or artist_names(item),
                            "thumbnail": YoutubeResponseMapper.select_thumbnail(
                                item.get("thumbnails", [])
                            ),
                        }
                    )
                elif item.get("podcastId"):
                    author = item.get("author")
                    items.append(
                        {
                            "type": "podcast",
                            "playlistId": item.get("podcastId", ""),
                            "browseId": item.get("browseId", ""),
                            "title": item.get("title", ""),
                            "subtitle": author.get("name", "") if isinstance(author, dict) else "",
                            "thumbnail": YoutubeResponseMapper.select_thumbnail(
                                item.get("thumbnails", [])
                            ),
                        }
                    )
                elif item.get("browseId"):
                    browse_id = item.get("browseId", "")
                    is_artist = browse_id.startswith("UC")
                    is_podcast_channel = browse_id.startswith("MPSP") or is_podcast
                    if is_podcast_channel and not is_artist:
                        item_type = "podcast"
                        playlist_id = browse_id[4:] if browse_id.startswith("MPSP") else browse_id
                    else:
                        item_type = "artist" if is_artist else "album"
                        playlist_id = ""
                    entry = {
                        "type": item_type,
                        "browseId": browse_id,
                        "title": item.get("title", ""),
                        "subtitle": artist_names(item) or item.get("year", ""),
                        "thumbnail": YoutubeResponseMapper.select_thumbnail(
                            item.get("thumbnails", [])
                        ),
                    }
                    if playlist_id:
                        entry["playlistId"] = playlist_id
                    items.append(entry)
            if items:
                sections.append({"title": title, "items": items})
        return jsonify({"sections": sections})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
