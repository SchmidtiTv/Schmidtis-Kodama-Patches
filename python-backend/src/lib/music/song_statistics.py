"""Application-facing song statistics formatting."""

from typing import TypedDict

from src.lib.providers.contracts import SongStatisticsProvider


class SongStatisticsResponse(TypedDict):
    """Stable JSON representation returned by the song statistics route."""

    views: str | None
    likes: str | None
    dislikes: str | None
    viewsRaw: int | None
    likesRaw: int | None
    dislikesRaw: int | None


class SongStatisticsService:
    """Present normalized provider statistics in Kodama's response format."""

    def __init__(self, provider: SongStatisticsProvider) -> None:
        self._provider = provider

    def get_statistics(self, video_id: str) -> SongStatisticsResponse:
        statistics = self._provider.get_statistics(video_id)
        return {
            "views": self._format_count(statistics.views),
            "likes": self._format_count(statistics.likes),
            "dislikes": self._format_count(statistics.dislikes),
            "viewsRaw": statistics.views,
            "likesRaw": statistics.likes,
            "dislikesRaw": statistics.dislikes,
        }

    @staticmethod
    def _format_count(count: int | None) -> str | None:
        if count is None:
            return None
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.1f}K"
        return str(count)
