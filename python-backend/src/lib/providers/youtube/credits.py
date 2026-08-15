"""YouTube public-description adapter for normalized song credits."""

import json
import re
from collections.abc import Mapping, Sequence

from src.lib.integrations.http import HttpResponse, HttpTransport, HttpTransportError
from src.lib.providers.errors import (
    ProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from src.lib.providers.models import SongCredits


class YoutubeSongCreditsProvider:
    """Resolve descriptions through InnerTube with a defensive watch-page fallback."""

    _INNERTUBE_URL = (
        "https://www.youtube.com/youtubei/v1/next?key=" "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
    )
    _WATCH_URL = "https://www.youtube.com/watch"
    _CLIENT_VERSION = "2.20240726.00.00"
    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    _TIMEOUT = (4.0, 8.0)
    _MAX_JSON_BYTES = 1 * 1024 * 1024
    _MAX_HTML_BYTES = 2 * 1024 * 1024

    def __init__(self, http: HttpTransport) -> None:
        self._http = http

    def get_credits(self, video_id: str) -> SongCredits:
        failures: list[ProviderError] = []
        try:
            description = self._from_innertube(video_id)
            if description:
                return SongCredits(description)
        except ProviderError as error:
            failures.append(error)

        try:
            return SongCredits(self._from_watch_page(video_id))
        except ProviderError as error:
            failures.append(error)

        if any(isinstance(error, ProviderUnavailableError) for error in failures):
            raise ProviderUnavailableError() from None
        raise ProviderResponseError() from None

    def _from_innertube(self, video_id: str) -> str:
        payload = {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": self._CLIENT_VERSION,
                    "hl": "en",
                    "gl": "US",
                }
            },
        }
        response = self._request(
            "POST",
            self._INNERTUBE_URL,
            max_bytes=self._MAX_JSON_BYTES,
            accepted_content_types=("application/json",),
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": self._USER_AGENT,
                "X-YouTube-Client-Name": "1",
                "X-YouTube-Client-Version": self._CLIENT_VERSION,
            },
        )
        try:
            data = json.loads(response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProviderResponseError() from None
        if not isinstance(data, Mapping):
            raise ProviderResponseError()
        return self._description_from_next(data)

    def _from_watch_page(self, video_id: str) -> str:
        response = self._request(
            "GET",
            self._WATCH_URL,
            max_bytes=self._MAX_HTML_BYTES,
            accepted_content_types=("text/html", "application/xhtml+xml"),
            params={"v": video_id},
            headers={
                "Accept": "text/html",
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": self._USER_AGENT,
            },
        )
        try:
            html = response.decode("utf-8")
        except UnicodeDecodeError:
            raise ProviderResponseError() from None
        match = re.search(r"ytInitialPlayerResponse\s*=\s*", html)
        if match is None:
            raise ProviderResponseError()
        try:
            player, _ = json.JSONDecoder().raw_decode(html[match.end() :].lstrip())
        except json.JSONDecodeError:
            raise ProviderResponseError() from None
        if not isinstance(player, Mapping):
            raise ProviderResponseError()
        details = player.get("videoDetails")
        if not isinstance(details, Mapping):
            raise ProviderResponseError()
        description = details.get("shortDescription", "")
        if not isinstance(description, str):
            raise ProviderResponseError()
        return description.strip()

    def _request(
        self,
        method: str,
        url: str,
        *,
        max_bytes: int,
        accepted_content_types: tuple[str, ...],
        **options: object,
    ) -> bytes:
        try:
            response = self._http.request(
                method,
                url,
                timeout=self._TIMEOUT,
                allow_redirects=False,
                stream=True,
                **options,
            )
        except HttpTransportError:
            raise ProviderUnavailableError() from None
        if response.status_code != 200:
            response.close()
            raise ProviderResponseError()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if content_type not in accepted_content_types:
            response.close()
            raise ProviderResponseError()
        return self._read_limited(response, max_bytes)

    @staticmethod
    def _read_limited(response: HttpResponse, limit: int) -> bytes:
        try:
            raw_length = response.headers.get("Content-Length")
            if raw_length:
                try:
                    if int(raw_length) > limit:
                        raise ProviderResponseError()
                except ValueError:
                    raise ProviderResponseError() from None
            content = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise ProviderResponseError()
            return bytes(content)
        finally:
            response.close()

    @staticmethod
    def _description_from_next(data: Mapping[str, object]) -> str:
        current: object = data.get("contents")
        for key in ("twoColumnWatchNextResults", "results", "results", "contents"):
            if not isinstance(current, Mapping):
                return ""
            current = current.get(key)
        if not isinstance(current, Sequence) or isinstance(current, (str, bytes)):
            return ""
        for item in current:
            if not isinstance(item, Mapping):
                continue
            renderer = item.get("videoSecondaryInfoRenderer")
            if not isinstance(renderer, Mapping):
                continue
            attributed = renderer.get("attributedDescription")
            if isinstance(attributed, Mapping):
                content = attributed.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            description = renderer.get("description")
            if not isinstance(description, Mapping):
                continue
            runs = description.get("runs")
            if not isinstance(runs, Sequence) or isinstance(runs, (str, bytes)):
                continue
            text = "".join(
                run_text
                for run in runs
                if isinstance(run, Mapping) and isinstance((run_text := run.get("text")), str)
            ).strip()
            if text:
                return text
        return ""
