"""Resolve a music group's members and public portraits."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

import requests

from src.config import Config, config_dirs

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2"
WIKIDATA_URL = "https://www.wikidata.org/wiki/Special:EntityData"
WIKIMEDIA_COMMONS_URL = "https://commons.wikimedia.org/w/api.php"
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Kodama/1.0 (+https://github.com/KiyoshiTheDevil/Kodama)",
}
REQUEST_TIMEOUT = (2, 4)
MAX_DETAIL_WORKERS = 6


class BandMemberLookupError(Exception):
    """Raised when a required third-party lookup cannot be completed."""


class JsonResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> object: ...


@dataclass
class BandMember:
    """A MusicBrainz person related to a group."""

    id: str
    name: str
    roles: list[str] = field(default_factory=list)
    membership_dates: list[str] = field(default_factory=list)
    image: str | None = None
    wikipedia_url: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "roles": self.roles,
            "membershipDates": self.membership_dates,
            "image": self.image,
            "wikipediaUrl": self.wikipedia_url,
        }


class BandMemberFinder:
    """MusicBrainz/Wikimedia boundary for group-member information."""

    def __init__(
        self,
        get: Callable[..., JsonResponse] = requests.get,
        monotonic: Callable[[], float] = time.monotonic,
        wall_time: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        cache_ttl: float = Config.BAND_MEMBER_CACHE_TTL,
        cache_dir: Path | None = None,
    ) -> None:
        self._get = get
        self._monotonic = monotonic
        self._wall_time = wall_time
        self._sleep = sleep
        self._cache_ttl = cache_ttl
        self._cache_dir = cache_dir or config_dirs.BAND_MEMBER_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._member_cache: dict[str, tuple[float, list[dict[str, object]]]] = {}
        self._cache_lock = Lock()
        self._musicbrainz_lock = Lock()
        self._last_musicbrainz_request = 0.0

    def find(self, artist_name: str) -> list[dict[str, object]]:
        cache_key = artist_name.strip().casefold()
        cached_members = self._cached_members(cache_key)
        if cached_members is not None:
            return cached_members

        group = self._find_group(artist_name)
        if not group:
            return self._cache_members(cache_key, [])

        group_id = group.get("id")
        if not isinstance(group_id, str):
            return self._cache_members(cache_key, [])
        group_data = self._get_json(
            f"{MUSICBRAINZ_URL}/artist/{group_id}", {"inc": "artist-rels", "fmt": "json"}
        )
        members = self._combine_relations(group_data.get("relations", []))
        self._load_member_details(members)
        return self._cache_members(cache_key, [member.as_dict() for member in members])

    def _load_member_details(self, members: list[BandMember]) -> None:
        if not members:
            return
        worker_count = min(len(members), MAX_DETAIL_WORKERS)
        with ThreadPoolExecutor(
            max_workers=worker_count, thread_name_prefix="band-member"
        ) as executor:
            details = executor.map(self._find_member_details, (member.id for member in members))
            for member, (image, wikipedia_url) in zip(members, details, strict=False):
                member.image = image
                member.wikipedia_url = wikipedia_url

    def _cached_members(self, cache_key: str) -> list[dict[str, object]] | None:
        with self._cache_lock:
            entry = self._member_cache.get(cache_key)
            if entry:
                saved_at, members = entry
                if self._monotonic() - saved_at < self._cache_ttl:
                    return deepcopy(members)
                del self._member_cache[cache_key]

            members = self._load_disk_cache(cache_key)
            if members is None:
                return None
            self._member_cache[cache_key] = (self._monotonic(), deepcopy(members))
            return members

    def _cache_members(
        self, cache_key: str, members: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        with self._cache_lock:
            self._member_cache[cache_key] = (self._monotonic(), deepcopy(members))
            self._save_disk_cache(cache_key, members)
        return members

    def _cache_path(self, cache_key: str) -> Path:
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{digest}.json"

    def _load_disk_cache(self, cache_key: str) -> list[dict[str, object]] | None:
        path = self._cache_path(cache_key)
        try:
            if self._wall_time() - path.stat().st_mtime >= self._cache_ttl:
                path.unlink(missing_ok=True)
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return None
        if not isinstance(payload, dict) or payload.get("artist") != cache_key:
            return None
        members = payload.get("members")
        if not isinstance(members, list) or any(not isinstance(member, dict) for member in members):
            return None
        return deepcopy(members)

    def _save_disk_cache(self, cache_key: str, members: list[dict[str, object]]) -> None:
        path = self._cache_path(cache_key)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._cache_dir,
                prefix=f".{path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                json.dump({"artist": cache_key, "members": members}, temporary, ensure_ascii=False)
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, path)
        except (OSError, TypeError, ValueError):
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _find_group(self, artist_name: str) -> dict[str, object] | None:
        search = self._get_json(
            f"{MUSICBRAINZ_URL}/artist/",
            {"query": f"artist:{artist_name} AND type:group", "fmt": "json", "limit": 5},
        )
        artists = search.get("artists", [])
        return artists[0] if artists and isinstance(artists[0], dict) else None

    def _combine_relations(self, relations: object) -> list[BandMember]:
        members: dict[str, BandMember] = {}
        if not isinstance(relations, list):
            return []
        for relation in relations:
            if not isinstance(relation, dict) or relation.get("type") != "member of band":
                continue
            if relation.get("ended"):
                continue
            artist = relation.get("artist")
            if relation.get("target-type") != "artist" or not isinstance(artist, dict):
                continue
            member_id = artist.get("id")
            name = artist.get("name")
            if not isinstance(member_id, str) or not isinstance(name, str):
                continue
            member = members.setdefault(member_id, BandMember(id=member_id, name=name))
            for role in relation.get("attributes", []):
                if isinstance(role, str) and role not in member.roles:
                    member.roles.append(role)
            date_range = self._date_range(relation)
            if date_range not in member.membership_dates:
                member.membership_dates.append(date_range)
        return list(members.values())

    @staticmethod
    def _date_range(relation: dict[str, object]) -> str:
        start = relation.get("begin") if isinstance(relation.get("begin"), str) else "Unknown start"
        return f"{start} \N{EN DASH} present"

    def _find_member_details(self, member_id: str) -> tuple[str | None, str | None]:
        try:
            artist = self._get_json(
                f"{MUSICBRAINZ_URL}/artist/{member_id}", {"inc": "url-rels", "fmt": "json"}
            )
            wikidata_id = self._wikidata_id(artist.get("relations", []))
            if not wikidata_id:
                return None, None
            entity = self._get_json(f"{WIKIDATA_URL}/{wikidata_id}.json")
            entities = entity.get("entities")
            entity_data = entities.get(wikidata_id) if isinstance(entities, dict) else None
            claims = entity_data.get("claims") if isinstance(entity_data, dict) else None
            wikipedia_url = self._wikipedia_url(entity_data)
            image_name = self._image_name(claims)
            if not image_name:
                return None, wikipedia_url
            image = self._find_commons_image(image_name)
            return image, wikipedia_url
        except (AttributeError, BandMemberLookupError, IndexError, StopIteration, TypeError):
            # A missing Wikidata link or portrait should not hide a member.
            return None, None

    def _find_commons_image(self, image_name: str) -> str | None:
        try:
            commons = self._get_json(
                WIKIMEDIA_COMMONS_URL,
                {
                    "action": "query",
                    "format": "json",
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "iiurlwidth": "600",
                    "titles": f"File:{image_name}",
                },
            )
            query = commons.get("query")
            pages = query.get("pages") if isinstance(query, dict) else None
            page = next(iter(pages.values()), {}) if isinstance(pages, dict) else {}
            image_info = page.get("imageinfo", [{}])[0] if isinstance(page, dict) else {}
            return image_info.get("thumburl") or image_info.get("url")
        except (AttributeError, BandMemberLookupError, IndexError, StopIteration, TypeError):
            return None

    @staticmethod
    def _wikidata_id(relations: object) -> str | None:
        if not isinstance(relations, list):
            return None
        for relation in relations:
            if not isinstance(relation, dict) or relation.get("type") != "wikidata":
                continue
            url = relation.get("url")
            resource = url.get("resource") if isinstance(url, dict) else None
            if isinstance(resource, str):
                identifier = resource.rsplit("/", 1)[-1]
                if identifier.startswith("Q") and identifier[1:].isdigit():
                    return identifier
        return None

    @staticmethod
    def _image_name(claims: object) -> str | None:
        if not isinstance(claims, dict):
            return None
        images = claims.get("P18", [])
        if not isinstance(images, list) or not images:
            return None
        image = images[0]
        if not isinstance(image, dict):
            return None
        mainsnak = image.get("mainsnak")
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else None
        value = datavalue.get("value") if isinstance(datavalue, dict) else None
        return value if isinstance(value, str) else None

    @staticmethod
    def _wikipedia_url(entity: object) -> str | None:
        if not isinstance(entity, dict):
            return None
        sitelinks = entity.get("sitelinks")
        if not isinstance(sitelinks, dict):
            return None
        english = sitelinks.get("enwiki")
        if isinstance(english, dict) and isinstance(english.get("url"), str):
            return english["url"]
        for key, sitelink in sitelinks.items():
            if (
                key.endswith("wiki")
                and isinstance(sitelink, dict)
                and isinstance(sitelink.get("url"), str)
            ):
                return sitelink["url"]
        return None

    def _get_json(self, url: str, params: dict[str, object] | None = None) -> dict[str, Any]:
        try:
            if url.startswith(MUSICBRAINZ_URL):
                self._wait_for_musicbrainz()
            response = self._get(
                url, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, AttributeError) as error:
            raise BandMemberLookupError from error
        if not isinstance(payload, dict):
            raise BandMemberLookupError
        return payload

    def _wait_for_musicbrainz(self) -> None:
        with self._musicbrainz_lock:
            wait_seconds = 1 - (self._monotonic() - self._last_musicbrainz_request)
            if wait_seconds > 0:
                self._sleep(wait_seconds)
            self._last_musicbrainz_request = self._monotonic()
