"""Lyrics lookup, transformation, and local custom-lyrics storage."""

import base64
import collections
import contextlib
import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path
from typing import Protocol, TypeVar, cast

import requests

from src.config import config_dirs, config_lyrics
from src.lib.integrations.musixmatch import MusixMatch
from src.lib.runtime.cache import CacheSettings
from src.lib.runtime.metadata_cache import MetadataCache

CacheValue = TypeVar("CacheValue")


class KakasiConverter(Protocol):
    def convert(self, text: str) -> list[dict[str, str]]: ...


class LyricsService:
    """Owns lyric providers and the small in-memory caches they need.

    Old server.py: get_lyrics, unison_versions, romanize_lyrics,
    translate_lyrics, and the /lyrics/custom handlers.
    """

    UNISON_BASE_URL = "https://unison.boidu.dev"

    def __init__(
        self,
        cache_settings: CacheSettings,
        musixmatch: MusixMatch,
        metadata_cache: MetadataCache | None = None,
    ) -> None:
        self._cache_settings = cache_settings
        self._musixmatch = musixmatch
        self._metadata_cache = metadata_cache or MetadataCache(config_dirs.CACHE_DATABASE)
        self._translation_cache: collections.OrderedDict[str, list[str]] = collections.OrderedDict()
        self._romaji_cache: collections.OrderedDict[str, str] = collections.OrderedDict()
        self._kakasi: KakasiConverter | None = None
        self._japanese_characters = re.compile(
            r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uff66-\uff9f]"
        )

    @staticmethod
    def _cache_key(title: str, artist: str, source: str) -> str:
        raw = f"{title.lower().strip()}|{artist.lower().strip()}|{source}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_path(self, title: str, artist: str, source: str) -> Path:
        return config_dirs.LYRICS_CACHE_DIR / f"{self._cache_key(title, artist, source)}.json"

    def _lyrics_cache_enabled(self) -> bool:
        return self._cache_settings.enabled.get("lyrics", True)

    def get_lyrics(
        self,
        title: str,
        artist: str,
        album: str,
        duration: str,
        source: str,
        video_id: str,
    ) -> dict[str, object]:
        """Look up lyrics in the existing provider priority order."""
        cache_path = self._cache_path(title, artist, source)
        cache_key = self._cache_key(title, artist, source)
        if self._lyrics_cache_enabled():
            try:
                cached = self._metadata_cache.get("lyrics", cache_key)
            except (OSError, sqlite3.Error):
                cached = None
            if cached is not None:
                return cached
        if self._lyrics_cache_enabled() and cache_path.exists():
            try:
                with cache_path.open(encoding="utf-8") as cache_file:
                    cached = cast("dict[str, object]", json.load(cache_file))
                self._metadata_cache.put("lyrics", cache_key, cached)
                cache_path.unlink(missing_ok=True)
                return cached
            except (OSError, sqlite3.Error, ValueError, TypeError):
                pass

        result = self._lookup_lrclib(title, artist, source)
        if not result:
            result = self._lookup_better_lyrics(title, artist, album, duration, source)
        if not result:
            result = self._lookup_portato(title, artist, album, duration, source)
        if not result:
            result = self._lookup_paxsenix_netease(title, artist, duration, source)
        if not result:
            result = self._lookup_kugou(title, artist, duration, source)
        if not result and source in ("auto", "musixmatch"):
            try:
                result = self._musixmatch.lookup(title, artist, duration)
            except Exception as error:
                print(f"[lyrics] Musixmatch error: {error}", flush=True)
        if not result:
            result = self._lookup_unison(title, artist, album, duration, source, video_id)
        if not result:
            result = self._lookup_simpmusic(source, video_id)

        if not result:
            return {"source": None, "synced": None, "plain": None}

        if self._lyrics_cache_enabled():
            with contextlib.suppress(OSError, sqlite3.Error, ValueError, TypeError):
                self._metadata_cache.put("lyrics", cache_key, result)
        return result

    @staticmethod
    def _lookup_lrclib(title: str, artist: str, source: str) -> dict[str, object] | None:
        if source not in ("auto", "lrclib"):
            return None
        try:
            response = requests.get(
                "https://lrclib.net/api/get",
                params={"artist_name": artist, "track_name": title},
                timeout=8,
            )
            if response.ok:
                data = response.json()
                if data.get("syncedLyrics"):
                    return {"source": "LRCLIB", "synced": data["syncedLyrics"], "plain": None}
                if data.get("plainLyrics"):
                    return {"source": "LRCLIB", "synced": None, "plain": data["plainLyrics"]}
        except Exception as error:
            print(f"[lyrics] LRCLIB error: {error}", flush=True)
        return None

    @staticmethod
    def _lookup_better_lyrics(
        title: str, artist: str, album: str, duration: str, source: str
    ) -> dict[str, object] | None:
        if source not in ("auto", "better"):
            return None
        try:
            params = {"s": title, "a": artist}
            if album:
                params["al"] = album
            if duration:
                params["d"] = duration
            response = requests.get(
                "https://lyrics-api.boidu.dev/getLyrics", params=params, timeout=8
            )
            data: dict[str, object] = (
                cast("dict[str, object]", response.json()) if response.ok else {}
            )
            if data.get("ttml"):
                return {"source": "Better Lyrics", "ttml": data["ttml"]}
        except Exception as error:
            print(f"[lyrics] Better Lyrics error: {error}", flush=True)
        return None

    @staticmethod
    def _lookup_portato(
        title: str, artist: str, album: str, duration: str, source: str
    ) -> dict[str, object] | None:
        if source not in ("auto", "portato"):
            return None
        try:
            params = {"s": title, "a": artist}
            if album:
                params["al"] = album
            if duration:
                params["d"] = duration
            response = requests.get(
                "https://lyrics-api.boidu.dev/qq/getLyrics",
                params=params,
                timeout=8,
            )
            raw = (response.json() or {}).get("lyrics", "") if response.ok else ""
            match = re.search(r'LyricContent="(.*?)"\s*/>', raw, re.DOTALL)
            if match:
                qrc = html.unescape(match.group(1))
                if qrc.strip():
                    return {"source": "Better Lyrics Portato", "qrc": qrc}
        except Exception as error:
            print(f"[lyrics] Portato error: {error}", flush=True)
        return None

    @staticmethod
    def _pick_paxsenix_song(
        songs: list[dict[str, object]], title: str, artist: str, wanted_duration_ms: int
    ) -> dict[str, object] | None:
        def normalize(value: object) -> str:
            return re.sub(r"[^0-9a-z一-鿿぀-ヿ]+", "", str(value or "").lower())

        wanted_title = normalize(title)
        wanted_artist = normalize(artist)
        best_song: dict[str, object] | None = None
        best_score = -1

        for song in songs:
            name = normalize(song.get("name"))
            raw_artists = song.get("artists")
            artist_names = (
                " ".join(
                    str(item.get("name", "")) for item in raw_artists if isinstance(item, dict)
                )
                if isinstance(raw_artists, list)
                else ""
            )
            artists = normalize(artist_names)
            if wanted_title and name and not (wanted_title in name or name in wanted_title):
                continue
            if (
                wanted_artist
                and artists
                and not (wanted_artist in artists or artists in wanted_artist)
            ):
                continue

            score = 10
            if name == wanted_title:
                score += 5
            raw_duration = song.get("duration")
            if wanted_duration_ms and isinstance(raw_duration, int | float):
                difference = abs(raw_duration - wanted_duration_ms)
                if difference <= 3_000:
                    score += 5
                elif difference <= 10_000:
                    score += 2
                else:
                    score -= 4
            if score > best_score:
                best_song = song
                best_score = score

        return best_song

    @classmethod
    def _lookup_paxsenix_netease(
        cls, title: str, artist: str, duration: str, source: str
    ) -> dict[str, object] | None:
        if source not in ("auto", "paxsenix-netease"):
            return None
        try:
            response = requests.get(
                "https://lyrics.paxsenix.org/netease/search",
                params={"q": f"{title} {artist}".strip()},
                timeout=5,
            )
            raw_songs = (
                ((response.json() or {}).get("result") or {}).get("songs") or []
                if response.ok
                else []
            )
            songs = [song for song in raw_songs if isinstance(song, dict)]
            wanted_duration_ms = int(float(duration) * 1000) if duration else 0
            song = cls._pick_paxsenix_song(songs, title, artist, wanted_duration_ms)
            song_id = song.get("id") if song else None
            if not song_id:
                return None
            lyrics_response = requests.get(
                "https://lyrics.paxsenix.org/netease/lyrics",
                params=cast("dict[str, str | int]", {"id": song_id, "word": "true"}),
                timeout=5,
            )
            data = lyrics_response.json() if lyrics_response.ok else None
            if isinstance(data, list) and data:
                return {"source": "NetEase (Paxsenix)", "netease": data}
        except Exception as error:
            print(f"[lyrics] Paxsenix NetEase error: {error}", flush=True)
        return None

    @staticmethod
    def _lookup_kugou(
        title: str, artist: str, duration: str, source: str
    ) -> dict[str, object] | None:
        if source not in ("auto", "kugou"):
            return None
        try:
            keyword = f"{title} {artist}".strip()
            duration_ms = int(float(duration) * 1000) if duration else 0
            search_response = requests.get(
                "https://songsearch.kugou.com/song_search_v2",
                params={"keyword": keyword, "page": 1, "pagesize": 5},
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if not search_response.ok:
                return None
            songs = json.loads(search_response.text.strip()).get("data", {}).get("lists", [])
            if not songs:
                return None
            candidate_response = requests.get(
                "https://lyrics.kugou.com/search",
                params={
                    "ver": 1,
                    "man": "yes",
                    "client": "pc",
                    "keyword": f"{title} - {artist}",
                    "duration": duration_ms,
                    "hash": songs[0].get("FileHash", ""),
                },
                timeout=8,
            )
            candidates: list[dict[str, object]] = []
            if candidate_response.ok:
                raw_candidates = cast("dict[str, object]", candidate_response.json()).get(
                    "candidates"
                )
                if isinstance(raw_candidates, list):
                    candidates = [
                        candidate for candidate in raw_candidates if isinstance(candidate, dict)
                    ]
            if not candidates:
                return None
            candidate = candidates[0]
            candidate_id = candidate.get("id")
            access_key = candidate.get("accesskey")
            if not isinstance(candidate_id, str | int) or not isinstance(access_key, str):
                return None
            download_response = requests.get(
                "https://lyrics.kugou.com/download",
                params={
                    "ver": 1,
                    "client": "pc",
                    "id": candidate_id,
                    "accesskey": access_key,
                    "fmt": "lrc",
                    "charset": "utf8",
                },
                timeout=8,
            )
            content = download_response.json().get("content", "") if download_response.ok else ""
            if content:
                lyrics = base64.b64decode(content).decode("utf-8", errors="ignore")
                if lyrics.strip():
                    return {"source": "Kugou", "synced": lyrics, "plain": None}
        except Exception as error:
            print(f"[lyrics] Kugou error: {error}", flush=True)
        return None

    def _lookup_unison(
        self, title: str, artist: str, album: str, duration: str, source: str, video_id: str
    ) -> dict[str, object] | None:
        if source not in ("auto", "unison"):
            return None
        try:
            item: dict[str, object] | None = None
            if video_id:
                response = requests.get(
                    f"{self.UNISON_BASE_URL}/lyrics", params={"v": video_id}, timeout=8
                )
                data: dict[str, object] = (
                    cast("dict[str, object]", response.json()) if response.ok else {}
                )
                if data.get("success") and isinstance(data.get("data"), dict):
                    item = cast("dict[str, object]", data["data"])
            if not item:
                params = {"song": title, "artist": artist}
                if album:
                    params["album"] = album
                if duration:
                    params["duration"] = duration
                response = requests.get(
                    f"{self.UNISON_BASE_URL}/lyrics/search", params=params, timeout=8
                )
                data: dict[str, object] = (
                    cast("dict[str, object]", response.json()) if response.ok else {}
                )
                raw_matches = data.get("data")
                if data.get("success") and isinstance(raw_matches, list) and raw_matches:
                    first_match = raw_matches[0]
                    item = first_match if isinstance(first_match, dict) else None
            if not item or not item.get("lyrics"):
                return None
            submitter = item.get("submitter")
            key_id = submitter.get("keyId") if isinstance(submitter, dict) else None
            submitter_name = self.display_name(key_id if isinstance(key_id, str) else None)
            if item.get("format") == "ttml":
                return {"source": "Unison", "ttml": item["lyrics"], "submitterName": submitter_name}
            if item.get("format") == "lrc":
                return {
                    "source": "Unison",
                    "synced": item["lyrics"],
                    "plain": None,
                    "submitterName": submitter_name,
                }
            if item.get("format") == "plain":
                return {
                    "source": "Unison",
                    "synced": None,
                    "plain": item["lyrics"],
                    "submitterName": submitter_name,
                }
        except Exception as error:
            print(f"[lyrics] Unison error: {error}", flush=True)
        return None

    @staticmethod
    def _lookup_simpmusic(source: str, video_id: str) -> dict[str, object] | None:
        if source not in ("auto", "simp") or not video_id:
            return None
        try:
            response = requests.get(f"https://api-lyrics.simpmusic.org/v1/{video_id}", timeout=8)
            data: dict[str, object] = (
                cast("dict[str, object]", response.json()) if response.ok else {}
            )
            items = data.get("data")
            item = items[0] if isinstance(items, list) and items else None
            if item and item.get("syncedLyrics"):
                return {"source": "SimpMusic", "synced": item["syncedLyrics"], "plain": None}
            if item and item.get("plainLyric"):
                return {"source": "SimpMusic", "synced": None, "plain": item["plainLyric"]}
        except Exception as error:
            print(f"[lyrics] SimpMusic error: {error}", flush=True)
        return None

    def display_name(self, key_id: str | None) -> str | None:
        """Resolve an Unison submitter's current public display name."""
        if not key_id:
            return None
        try:
            response = requests.get(f"{self.UNISON_BASE_URL}/leaderboard/users/{key_id}", timeout=5)
            if response.ok:
                return response.json().get("data", {}).get("displayName")
        except Exception:
            pass
        return None

    def unison_versions(
        self, video_id: str, title: str, artist: str, album: str, duration: str
    ) -> list[dict[str, object]]:
        """Fetch the available community lyric submissions for one track."""
        candidates: list[dict[str, object]] = []
        seen: set[object] = set()

        def add(item: object) -> None:
            if not isinstance(item, dict):
                return
            candidate_id = item.get("id")
            key = (
                candidate_id if candidate_id is not None else hash(item.get("lyrics") or repr(item))
            )
            if key not in seen:
                seen.add(key)
                candidates.append(item)

        def search(params: dict[str, str]) -> list[dict[str, object]]:
            try:
                response = requests.get(
                    f"{self.UNISON_BASE_URL}/lyrics/search", params=params, timeout=8
                )
                data: dict[str, object] = (
                    cast("dict[str, object]", response.json()) if response.ok else {}
                )
                raw_matches = data.get("data")
                if data.get("success") and isinstance(raw_matches, list):
                    return [item for item in raw_matches if isinstance(item, dict)]
            except Exception:
                pass
            return []

        try:
            if video_id:
                response = requests.get(
                    f"{self.UNISON_BASE_URL}/lyrics", params={"v": video_id}, timeout=8
                )
                data: dict[str, object] = (
                    cast("dict[str, object]", response.json()) if response.ok else {}
                )
                if data.get("success"):
                    direct_matches = data.get("data")
                    if isinstance(direct_matches, dict):
                        add(direct_matches)
                    elif isinstance(direct_matches, list):
                        for item in direct_matches:
                            add(item)

            strict_params = {"song": title, "artist": artist}
            if album:
                strict_params["album"] = album
            if duration:
                strict_params["duration"] = duration
            for item in search(strict_params):
                add(item)

            artist_lower, title_lower = artist.lower(), title.lower()
            for item in search({"q": f"{title} {artist}".strip()}):
                artist_value = item.get("artist")
                title_value = item.get("song") or item.get("title")
                item_artist = artist_value.lower() if isinstance(artist_value, str) else ""
                item_title = title_value.lower() if isinstance(title_value, str) else ""
                if (
                    artist_lower
                    and item_artist
                    and (artist_lower in item_artist or item_artist in artist_lower)
                    and title_lower
                    and item_title
                    and (title_lower in item_title or item_title in title_lower)
                ):
                    add(item)
        except Exception as error:
            print(f"[lyrics] Unison versions error: {error}", flush=True)

        versions: list[dict[str, object]] = []
        name_cache: dict[object, str | None] = {}
        for item in candidates[:8]:
            lyrics = item.get("lyrics")
            lyric_format = item.get("format")
            sync_type = item.get("syncType")
            candidate_id = item.get("id")
            submitter = cast("dict[str, object]", item.get("submitter") or {})
            if not lyrics and candidate_id is not None:
                try:
                    response = requests.get(
                        f"{self.UNISON_BASE_URL}/lyrics/{candidate_id}", timeout=6
                    )
                    full_data = (response.json() or {}).get("data") or {} if response.ok else {}
                    lyrics = full_data.get("lyrics")
                    lyric_format = full_data.get("format") or lyric_format
                    sync_type = full_data.get("syncType") or sync_type
                    submitter = full_data.get("submitter") or submitter
                except Exception:
                    pass
            if not lyrics:
                continue
            key_value = submitter.get("keyId")
            key_id = key_value if isinstance(key_value, str) else None
            if key_id not in name_cache:
                name_cache[key_id] = self.display_name(key_id)
            versions.append(
                {
                    "id": candidate_id,
                    "format": lyric_format,
                    "syncType": sync_type,
                    "lyrics": lyrics,
                    "submitterName": name_cache[key_id],
                    "voteCount": item.get("voteCount"),
                }
            )
        return versions

    def romanize(self, lines: list[str]) -> list[str]:
        """Convert Japanese lyric lines to Hepburn romaji."""
        if self._kakasi is None:
            import pykakasi

            self._kakasi = cast("KakasiConverter", pykakasi.kakasi())

        result: list[str] = []
        for line in lines:
            if not line.strip() or not self._japanese_characters.search(line):
                result.append("")
                continue
            cache_key = f"romaji:{line}"
            if cache_key in self._romaji_cache:
                result.append(self._romaji_cache[cache_key])
                continue
            converted = self._kakasi.convert(line)
            romaji = " ".join(
                item.get("hepburn") or item.get("orig", "")
                for item in converted
                if (item.get("hepburn") or item.get("orig", "")).strip()
            )
            self._lru_put(self._romaji_cache, cache_key, romaji)
            result.append(romaji)
        return result

    def translate(self, lines: list[str], target_lang: str) -> list[str]:
        """Translate non-empty lyric lines through the existing Google endpoint."""
        non_empty_indices = [index for index, line in enumerate(lines) if line.strip()]
        non_empty_lines = [lines[index] for index in non_empty_indices]
        if not non_empty_lines:
            return list(lines)

        cache_key = f"{target_lang}:{hash(tuple(non_empty_lines))}"
        if cache_key in self._translation_cache:
            translated_lines = self._translation_cache[cache_key]
        else:
            translated_lines = self._google_translate_batch(non_empty_lines, target_lang)
            self._lru_put(self._translation_cache, cache_key, translated_lines)

        result = list(lines)
        for index, translated in zip(non_empty_indices, translated_lines, strict=False):
            result[index] = translated
        return result

    @staticmethod
    def _google_translate_batch(lines: list[str], target_lang: str) -> list[str]:
        language = config_lyrics.GOOGLE_LANGUAGE_CODES.get(target_lang, target_lang.lower())
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "auto",
                "tl": language,
                "dt": "t",
                "q": "\n".join(lines),
            },
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        translated = "".join(chunk[0] for chunk in response.json()[0] if chunk and chunk[0])
        translated_lines: list[str] = [str(line) for line in translated.split("\n")]
        while len(translated_lines) < len(lines):
            translated_lines.append("")
        return translated_lines[: len(lines)]

    @staticmethod
    def _lru_put(
        cache: collections.OrderedDict[str, CacheValue], key: str, value: CacheValue
    ) -> None:
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > config_lyrics.TRANSLATION_CACHE_MAX:
            cache.popitem(last=False)

    @staticmethod
    def get_custom(video_id: str) -> dict[str, str] | None:
        for extension in ("lrc", "ttml"):
            path = config_dirs.CUSTOM_LYRICS_DIR / f"{video_id}.{extension}"
            if path.is_file():
                return {"content": path.read_text(encoding="utf-8"), "format": extension}
        return None

    @staticmethod
    def save_custom(video_id: str, content: str, lyric_format: str) -> None:
        for extension in ("lrc", "ttml"):
            path = config_dirs.CUSTOM_LYRICS_DIR / f"{video_id}.{extension}"
            if path.is_file():
                path.unlink()
        (config_dirs.CUSTOM_LYRICS_DIR / f"{video_id}.{lyric_format}").write_text(
            content, encoding="utf-8"
        )

    @staticmethod
    def delete_custom(video_id: str) -> bool:
        deleted = False
        for extension in ("lrc", "ttml"):
            path = config_dirs.CUSTOM_LYRICS_DIR / f"{video_id}.{extension}"
            if path.is_file():
                path.unlink()
                deleted = True
        return deleted
