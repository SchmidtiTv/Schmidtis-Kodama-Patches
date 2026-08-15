"""Song statistics adapter for the Return YouTube Dislike API."""

from src.lib.integrations.http import HttpTransport, HttpTransportError

from .errors import ProviderResponseError, ProviderUnavailableError
from .models import SongStatistics


class ReturnYoutubeDislikeProvider:
    """Return normalized song statistics without leaking upstream details."""

    API_URL = "https://returnyoutubedislikeapi.com/votes"
    REQUEST_TIMEOUT_SECONDS = 5.0

    def __init__(self, http: HttpTransport) -> None:
        self._http = http

    def get_statistics(self, video_id: str) -> SongStatistics:
        try:
            response = self._http.request(
                "GET",
                self.API_URL,
                params={"videoId": video_id},
                headers={"Accept": "application/json"},
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
        except HttpTransportError:
            raise ProviderUnavailableError() from None

        if response.status_code != 200:
            raise ProviderResponseError()

        try:
            payload = response.json()
        except ValueError:
            raise ProviderResponseError() from None

        if not isinstance(payload, dict):
            raise ProviderResponseError()

        return SongStatistics(
            views=self._read_count(payload, "viewCount"),
            likes=self._read_count(payload, "likes"),
            dislikes=self._read_count(payload, "dislikes"),
        )

    @staticmethod
    def _read_count(payload: dict[object, object], field: str) -> int | None:
        value = payload.get(field)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ProviderResponseError()
        return value
