"""Discord-specific feedback webhook integration."""

import json
from typing import ClassVar, Protocol
from urllib.parse import urlsplit

from src.lib.feedback.models import FeedbackCategory, FeedbackSubmission
from src.lib.integrations.http import HttpTransport, HttpTransportError
from src.lib.providers.errors import (
    ProviderAuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)


class FeedbackWebhookClient(Protocol):
    def submit(self, submission: FeedbackSubmission) -> None: ...


class DiscordFeedbackWebhookClient:
    _COLORS: ClassVar[dict[FeedbackCategory, int]] = {
        FeedbackCategory.BUG: 0xE24B4A,
        FeedbackCategory.CRASH: 0xA32D2D,
        FeedbackCategory.DESIGN: 0x378ADD,
        FeedbackCategory.SUGGESTION: 0x1D9E75,
    }

    def __init__(self, http: HttpTransport, webhook_url: str) -> None:
        parsed = urlsplit(webhook_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Invalid feedback webhook configuration")
        self._http = http
        self._webhook_url = webhook_url

    def submit(self, submission: FeedbackSubmission) -> None:
        embed: dict[str, object] = {
            "title": submission.title or "(no title)",
            "description": submission.description or "—",
            "color": self._COLORS[submission.category],
            "fields": self._fields(submission),
        }
        if submission.reporter:
            embed["footer"] = {"text": f"from {submission.reporter}"}

        files: dict[str, tuple[str, bytes, str]] = {}
        if submission.screenshot is not None:
            extension = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
            }[submission.screenshot.content_type]
            filename = f"screenshot.{extension}"
            files["file_shot"] = (
                filename,
                submission.screenshot.content,
                submission.screenshot.content_type,
            )
            embed["image"] = {"url": f"attachment://{filename}"}
        if submission.diagnostic_logs:
            files["file_log"] = (
                "backend-log.txt",
                submission.diagnostic_logs,
                "text/plain",
            )

        payload = {"username": "Kodama Feedback", "embeds": [embed]}
        options: dict[str, object]
        timeout: tuple[float, float]
        if files:
            options = {"data": {"payload_json": json.dumps(payload)}, "files": files}
            timeout = (4.0, 11.0)
        else:
            options = {"json": payload}
            timeout = (4.0, 8.0)
        try:
            response = self._http.request(
                "POST",
                self._webhook_url,
                timeout=timeout,
                allow_redirects=False,
                **options,
            )
        except HttpTransportError:
            raise ProviderUnavailableError() from None
        if response.status_code in (401, 403):
            response.close()
            raise ProviderAuthenticationError()
        if not 200 <= response.status_code < 300:
            response.close()
            raise ProviderResponseError()
        response.close()

    @staticmethod
    def _fields(submission: FeedbackSubmission) -> list[dict[str, object]]:
        fields: list[dict[str, object]] = [
            {"name": "Category", "value": submission.category.value, "inline": True},
            {"name": "Version", "value": submission.application_version, "inline": True},
            {"name": "System", "value": submission.operating_system, "inline": True},
        ]
        if submission.severity:
            fields.append({"name": "Severity", "value": submission.severity, "inline": True})
        return fields
