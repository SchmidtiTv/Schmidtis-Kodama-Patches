"""Return the normalized YouTube Music home feed."""

from flask import jsonify

from src.lib import YoutubeResponseMapper
from src.lib.music.audio_versions import prefer_audio_versions

from . import blueprint
from ._formatters import is_podcast_section, song_result
from ._services import metadata_cache, music_session
from src.type_defs import RouteResponse


@blueprint.route("/home")
def get_home() -> RouteResponse:
    try:
        client = music_session().get_active_client()
        resolver = music_session().get_system_client()
        home = client.get_home(limit=15)

        # Resolve every section's video-variant songs to their audio counterparts in a single
        # pass over the whole feed, instead of once per section (each call spins up its own
        # thread pool): up to 15 sequential thread-pool bursts otherwise, on a cache-miss.
        section_raw_songs = [
            [
                item
                for item in section.get("contents", [])
                if item.get("videoId") and not is_podcast_section(section.get("title", ""))
            ]
            for section in home
        ]
        combined_songs = [song for songs in section_raw_songs for song in songs]
        resolved_combined = iter(
            prefer_audio_versions(resolver, None, combined_songs, metadata_cache())
        )
        section_resolved_songs = [
            [next(resolved_combined) for _ in songs] for songs in section_raw_songs
        ]

        sections = []
        for section, resolved_songs_list in zip(home, section_resolved_songs, strict=True):
            title = section.get("title", "")
            is_podcast = is_podcast_section(title)
            items = []
            resolved_songs = iter(resolved_songs_list)
            for item in section.get("contents", []):
                if item.get("videoId") and not is_podcast:
                    items.append(song_result(next(resolved_songs)))
                elif item.get("videoId"):
                    items.append(
                        {
                            "type": "podcast_episode",
                            "videoId": item.get("videoId", ""),
                            "browseId": item.get("browseId", ""),
                            "title": item.get("title", ""),
                            "subtitle": item.get("description", "") or item.get("date", ""),
                            "thumbnail": YoutubeResponseMapper.select_thumbnail(item.get("thumbnails", [])),
                        }
                    )
                elif item.get("playlistId"):
                    items.append(
                        {
                            "type": "podcast" if is_podcast else "playlist",
                            "playlistId": item.get("playlistId", ""),
                            "title": item.get("title", ""),
                            "subtitle": item.get("description", "")
                            or ", ".join(artist["name"] for artist in item.get("artists", [])),
                            "thumbnail": YoutubeResponseMapper.select_thumbnail(item.get("thumbnails", [])),
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
                            "thumbnail": YoutubeResponseMapper.select_thumbnail(item.get("thumbnails", [])),
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
                        "subtitle": ", ".join(artist["name"] for artist in item.get("artists", []))
                        or item.get("year", ""),
                        "thumbnail": YoutubeResponseMapper.select_thumbnail(item.get("thumbnails", [])),
                    }
                    if playlist_id:
                        entry["playlistId"] = playlist_id
                    items.append(entry)
            if items:
                sections.append({"title": title, "items": items})
        return jsonify({"sections": sections})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
