"""Resolve video-heavy YouTube Music playlists to their audio counterparts."""

import contextlib
import re
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from typing import Protocol, cast

from src.config import Config
from src.lib.music.video_variants import is_video_variant
from src.lib.runtime.metadata_cache import MetadataCache


class WatchPlaylistClient(Protocol):
    def get_watch_playlist(
        self, videoId: str | None = None, playlistId: str | None = None, limit: int = 25
    ) -> dict[str, object]: ...

    def search(
        self, query: str, filter: str = "songs", limit: int = 20
    ) -> list[dict[str, object]]: ...


_VIDEO_TITLE_MARKER = re.compile(
    r"\s*[\[(](?:(?:official\s+)?(?:hd\s+)?(?:music|lyric)\s+video|"
    r"official\s+video|(?:official\s+)?audio|(?:official\s+)?visualizer|preview|"
    r"offizielles?\s+musikvideo)[\])]\s*$",
    re.IGNORECASE,
)
_FEATURE_CREDIT = re.compile(r"\s*[\[(](?:feat(?:uring)?|ft)\.?\s+[^\])]+[\])]", re.IGNORECASE)
_FEATURE_CREDIT_CONTENT = re.compile(
    r"[\[(](?:feat(?:uring)?|ft)\.?\s+([^\])]+)[\])]", re.IGNORECASE
)
_PROTECTED_VERSION_MARKERS = {
    "acoustic",
    "edit",
    "extended",
    "live",
    "mix",
    "piano",
    "remix",
    "slowed",
    "sped up",
    "version",
}
_MIN_MATCH_SCORE = 0.78


def _normalized_text(value: object) -> str:
    return re.sub(r"[^\w]+", " ", str(value).casefold()).strip()


def _artist_names(track: Mapping[str, object]) -> set[str]:
    artists = track.get("artists")
    if not isinstance(artists, list):
        return set()
    return {
        _normalized_text(
            re.sub(r"\s+-\s+topic$", "", str(artist.get("name", "")), flags=re.IGNORECASE)
        )
        for artist in artists
        if isinstance(artist, dict) and artist.get("name")
    }


def _normalized_title(track: Mapping[str, object]) -> str:
    title = str(track.get("title", ""))
    title = _VIDEO_TITLE_MARKER.sub("", title)
    title = _FEATURE_CREDIT.sub("", title)

    # Official video titles often include "Artist - Song" even though search
    # song results contain only "Song". Strip the prefix only when it names a
    # credited artist, so genuine hyphenated titles remain intact.
    prefix, separator, remainder = title.partition(" - ")
    normalized_prefix = _normalized_text(prefix)
    if separator and any(
        artist in normalized_prefix or normalized_prefix in artist
        for artist in _artist_names(track)
    ):
        title = remainder
    return re.sub(r"[^\w]+", " ", title.casefold()).strip()


def _artists(track: Mapping[str, object]) -> set[str]:
    return _artist_names(track)


def _primary_artist(track: Mapping[str, object]) -> str:
    artists = track.get("artists")
    if not isinstance(artists, list) or not artists or not isinstance(artists[0], dict):
        return ""
    return str(artists[0].get("name", "")).strip()


def _same_song(video: Mapping[str, object], audio: Mapping[str, object]) -> bool:
    if _normalized_title(video) != _normalized_title(audio):
        return False
    video_artists = _artists(video)
    audio_artists = _artists(audio)
    return not video_artists or not audio_artists or bool(video_artists & audio_artists)


def _version_markers(title: str) -> set[str]:
    return {marker for marker in _PROTECTED_VERSION_MARKERS if marker in title}


def _feature_credits(track: Mapping[str, object]) -> set[str]:
    return {
        _normalized_text(credit)
        for credit in _FEATURE_CREDIT_CONTENT.findall(str(track.get("title", "")))
    }


def _title_similarity(video: Mapping[str, object], candidate: Mapping[str, object]) -> float:
    video_title = _normalized_title(video)
    candidate_title = _normalized_title(candidate)
    if not video_title or not candidate_title:
        return 0.0
    if video_title == candidate_title:
        return 1.0

    # Do not silently replace a specifically-labelled remix/live/etc. with the
    # base recording, even when the remaining title words are identical.
    if _version_markers(video_title) != _version_markers(candidate_title):
        return 0.0

    video_tokens = set(video_title.split())
    candidate_tokens = set(candidate_title.split())
    overlap = video_tokens & candidate_tokens
    if not overlap:
        return 0.0

    coverage = len(overlap) / min(len(video_tokens), len(candidate_tokens))
    jaccard = len(overlap) / len(video_tokens | candidate_tokens)
    sequence = SequenceMatcher(None, video_title, candidate_title).ratio()

    # Descriptive video titles such as "Artist - Song" or "I made a music
    # video in GTA 6" can contain the complete, shorter song title.
    containment = 0.86 if coverage == 1.0 else 0.0
    return max(sequence, containment, (coverage * 0.55) + (jaccard * 0.45))


def _duration_seconds(track: Mapping[str, object]) -> int | None:
    duration = track.get("duration_seconds")
    if isinstance(duration, int):
        return duration

    text = str(track.get("duration") or track.get("length") or "")
    parts = text.split(":")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def _audio_match_score(
    video: Mapping[str, object], candidate: Mapping[str, object]
) -> float | None:
    """Score a song hit while rejecting covers and mismatched versions."""
    if candidate.get("resultType") not in (None, "song"):
        return None
    if candidate.get("videoType") != "MUSIC_VIDEO_TYPE_ATV":
        return None

    video_artists = _artists(video)
    candidate_artists = _artists(candidate)
    if video_artists and candidate_artists and not video_artists & candidate_artists:
        return None

    title_score = _title_similarity(video, candidate)
    if title_score < 0.72:
        return None

    video_duration = _duration_seconds(video)
    candidate_duration = _duration_seconds(candidate)
    if video_duration is None or candidate_duration is None:
        duration_score = 0.5
    else:
        duration_score = max(0.0, 1.0 - (abs(video_duration - candidate_duration) / 180))

    if video_artists and candidate_artists:
        artist_score = len(video_artists & candidate_artists) / len(
            video_artists | candidate_artists
        )
    else:
        artist_score = 0.5
    feature_penalty = 0.04 if _feature_credits(video) != _feature_credits(candidate) else 0.0
    return (title_score * 0.75) + (artist_score * 0.20) + (duration_score * 0.05) - feature_penalty


def _search_query(track: Mapping[str, object]) -> str:
    raw_artists = track.get("artists")
    artists = raw_artists if isinstance(raw_artists, list) else []
    names = [str(artist.get("name", "")) for artist in artists if isinstance(artist, dict)]
    return " ".join(part for part in (str(track.get("title", "")), *names) if part).strip()


def _find_audio_search_match(
    client: object, video: Mapping[str, object]
) -> dict[str, object] | None:
    search_client = cast(WatchPlaylistClient, client)
    query = _search_query(video)
    primary_artist = _primary_artist(video)
    if not query or not primary_artist:
        return None

    # Featuring credits can make the fully-qualified query too narrow. Retry
    # with only the primary artist, while applying the same strict match rules.
    queries = [query, f"{video.get('title', '')} {primary_artist}".strip()]
    seen_queries: set[str] = set()
    for search_query in queries:
        normalized_query = search_query.casefold()
        if normalized_query in seen_queries:
            continue
        seen_queries.add(normalized_query)
        try:
            candidates = search_client.search(search_query, filter="songs", limit=10)
        except Exception as error:
            print(
                f"[playlist] audio search failed video_id={video.get('videoId', '')}: {error}",
                flush=True,
            )
            continue

        matches = [
            (score, candidate)
            for candidate in candidates
            if isinstance(candidate, dict)
            and (score := _audio_match_score(video, candidate)) is not None
            and score >= _MIN_MATCH_SCORE
        ]
        if matches:
            return max(matches, key=lambda match: cast(float, match[0]))[1]
    return None


def _watch_playlist_candidates(client: object, playlist_id: str, track_count: int) -> list[object]:
    watch_client = cast(WatchPlaylistClient, client)
    try:
        response = watch_client.get_watch_playlist(
            playlistId=playlist_id, limit=max(25, track_count)
        )
        candidates = response.get("tracks", [])
    except Exception as error:
        print(
            f"[playlist] audio counterpart lookup failed playlist_id={playlist_id}: {error}",
            flush=True,
        )
        return []

    return candidates if isinstance(candidates, list) else []


def _cached_counterpart(cache: MetadataCache | None, video_id: str) -> dict[str, object] | None:
    if cache is None or not video_id:
        return None
    try:
        return cache.get_audio_counterpart(video_id, Config.AUDIO_COUNTERPART_CACHE_TTL)
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return None


def _store_counterpart(
    cache: MetadataCache | None, video_id: str, audio: dict[str, object]
) -> None:
    if cache is None or not video_id:
        return
    with contextlib.suppress(OSError, sqlite3.Error, TypeError, ValueError):
        cache.put_audio_counterpart(video_id, audio)


def _delete_counterpart(cache: MetadataCache | None, video_id: str) -> None:
    if cache is None or not video_id:
        return
    with contextlib.suppress(OSError, sqlite3.Error):
        cache.delete_audio_counterpart(video_id)


def _resolve_audio_batch(
    client: object,
    candidates: list[object],
    tracks: Sequence[Mapping[str, object]],
    offset: int,
    counterpart_cache: MetadataCache | None = None,
) -> tuple[list[dict[str, object]], int]:
    """Resolve one ordered playlist batch without delaying other batches."""
    resolved = [dict(track) for track in tracks]
    replacement_count = 0
    unresolved: list[tuple[int, Mapping[str, object]]] = []
    for batch_index, video in enumerate(tracks):
        if not is_video_variant(video):
            continue
        video_id = str(video.get("videoId", ""))
        cached_audio = _cached_counterpart(counterpart_cache, video_id)
        if (
            cached_audio is not None
            and cached_audio.get("videoType") == "MUSIC_VIDEO_TYPE_ATV"
            and _same_song(video, cached_audio)
        ):
            resolved[batch_index] = cached_audio
            replacement_count += 1
            print(
                "[playlist] resolved audio counterpart "
                f"video_id={video_id} audio_id={cached_audio.get('videoId', '')} "
                f"title={cached_audio.get('title', '')!r} source=cache",
                flush=True,
            )
            continue
        if cached_audio is not None:
            _delete_counterpart(counterpart_cache, video_id)
        audio = candidates[offset + batch_index] if offset + batch_index < len(candidates) else None
        if (
            isinstance(audio, dict)
            and audio.get("videoType") == "MUSIC_VIDEO_TYPE_ATV"
            and _same_song(video, audio)
        ):
            resolved[batch_index] = audio
            replacement_count += 1
            _store_counterpart(counterpart_cache, video_id, audio)
            print(
                "[playlist] resolved audio counterpart "
                f"video_id={video.get('videoId', '')} audio_id={audio.get('videoId', '')} "
                f"title={audio.get('title', '')!r} source=watch-playlist",
                flush=True,
            )
            continue
        unresolved.append((batch_index, video))

    if not unresolved:
        return resolved, replacement_count

    # A playlist queue can retain the original video entries even with isAudioOnly
    # enabled. Resolve only this batch so the SSE route can emit earlier batches
    # while subsequent lookups run later.
    with ThreadPoolExecutor(max_workers=4) as executor:

        def find_match(item: tuple[int, Mapping[str, object]]) -> dict[str, object] | None:
            return _find_audio_search_match(client, item[1])

        search_matches = executor.map(find_match, unresolved)
        for (batch_index, video), audio in zip(unresolved, search_matches, strict=False):
            if audio is None:
                print(
                    "[playlist] audio counterpart unresolved "
                    f"video_id={video.get('videoId', '')} "
                    f"title={video.get('title', '')!r}",
                    flush=True,
                )
                continue
            resolved[batch_index] = audio
            replacement_count += 1
            video_id = str(video.get("videoId", ""))
            _store_counterpart(counterpart_cache, video_id, audio)
            print(
                "[playlist] resolved audio counterpart "
                f"video_id={video.get('videoId', '')} audio_id={audio.get('videoId', '')} "
                f"title={audio.get('title', '')!r} source=search",
                flush=True,
            )

    return resolved, replacement_count


def iter_preferred_audio_versions(
    client: object,
    playlist_id: str | None,
    tracks: Sequence[Mapping[str, object]],
    batch_size: int,
    counterpart_cache: MetadataCache | None = None,
) -> Iterator[list[dict[str, object]]]:
    """Yield ordered, audio-preferred track batches for an SSE playlist response."""
    if not tracks:
        return

    if not any(is_video_variant(track) for track in tracks):
        for index in range(0, len(tracks), batch_size):
            yield [dict(track) for track in tracks[index : index + batch_size]]
        return

    candidates = _watch_playlist_candidates(client, playlist_id, len(tracks)) if playlist_id else []
    candidate_count = sum(1 for track in tracks if is_video_variant(track))
    replacement_count = 0
    for index in range(0, len(tracks), batch_size):
        batch, replacements = _resolve_audio_batch(
            client,
            candidates,
            tracks[index : index + batch_size],
            index,
            counterpart_cache,
        )
        replacement_count += replacements
        yield batch

    print(
        f"[playlist] audio counterpart resolution playlist_id={playlist_id or 'none'} "
        f"replaced={replacement_count}/{candidate_count} "
        f"unresolved={candidate_count - replacement_count} total_tracks={len(tracks)}",
        flush=True,
    )


def prefer_audio_versions(
    client: object,
    playlist_id: str | None,
    tracks: Sequence[Mapping[str, object]],
    counterpart_cache: MetadataCache | None = None,
) -> list[dict[str, object]]:
    """Replace OMV/UGC playlist entries with their audio versions when available."""
    if not tracks or not any(is_video_variant(track) for track in tracks):
        return [dict(track) for track in tracks]

    candidate_count = sum(1 for track in tracks if is_video_variant(track))
    candidates = _watch_playlist_candidates(client, playlist_id, len(tracks)) if playlist_id else []
    resolved, replacement_count = _resolve_audio_batch(
        client, candidates, tracks, 0, counterpart_cache
    )

    print(
        f"[playlist] audio counterpart resolution playlist_id={playlist_id or 'none'} "
        f"replaced={replacement_count}/{candidate_count} "
        f"unresolved={candidate_count - replacement_count} total_tracks={len(tracks)}",
        flush=True,
    )
    return resolved
