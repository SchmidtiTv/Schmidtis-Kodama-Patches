"""Validation, diagnostics, and redaction policy for feedback submissions."""

import base64
import binascii
import re
from collections.abc import Callable, Mapping, Sequence

from src.lib.feedback.models import (
    FeedbackCategory,
    FeedbackScreenshot,
    FeedbackSubmission,
)
from src.lib.integrations.feedback_webhook import FeedbackWebhookClient

MAX_TITLE_LENGTH = 240
MAX_DESCRIPTION_LENGTH = 3900
MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024


class FeedbackValidationError(ValueError):
    pass


class FeedbackNotConfiguredError(RuntimeError):
    pass


class FeedbackService:
    def __init__(
        self,
        client: FeedbackWebhookClient | None,
        log_source: Callable[[], Sequence[str]],
    ) -> None:
        self._client = client
        self._log_source = log_source

    def submit(self, raw: object) -> None:
        if self._client is None:
            raise FeedbackNotConfiguredError()
        payload = self._mapping(raw)
        title = self._string(payload, "title").strip()
        description = self._string(payload, "description").strip()
        if not title and not description:
            raise FeedbackValidationError("empty")
        if len(title) > MAX_TITLE_LENGTH or len(description) > MAX_DESCRIPTION_LENGTH:
            raise FeedbackValidationError("feedback_too_large")
        category = self._category(payload.get("category", FeedbackCategory.BUG.value))
        include_logs = payload.get("includeLogs", True)
        if not isinstance(include_logs, bool):
            raise FeedbackValidationError("includeLogs must be boolean")
        screenshot = self._screenshot(payload.get("screenshot"))
        logs = self._diagnostic_logs() if include_logs else None
        submission = FeedbackSubmission(
            title=title,
            category=category,
            severity=self._limited_string(payload, "severity", 80),
            description=description,
            application_version=self._limited_string(payload, "version", 80, default="?"),
            operating_system=self._limited_string(payload, "os", 160, default="?"),
            reporter=self._limited_string(payload, "reporter", 80),
            include_logs=include_logs,
            screenshot=screenshot,
            diagnostic_logs=logs,
        )
        self._client.submit(submission)

    def _diagnostic_logs(self) -> bytes | None:
        lines = list(self._log_source())[-80:]
        if not lines:
            return None
        redacted = "\n".join(self._redact(line) for line in lines).encode("utf-8")
        return redacted[:MAX_LOG_BYTES]

    @staticmethod
    def _redact(line: str) -> str:
        value = re.sub(
            r"(?i)(authorization|cookie|set-cookie|x-goog-authuser|token|secret)\s*[:=]\s*\S+",
            r"\1=[REDACTED]",
            line,
        )
        value = re.sub(
            r"https://(?:discord(?:app)?\.com|discord\.com)/api/webhooks/\S+",
            "[REDACTED_WEBHOOK]",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(r"(?i)(?:profiles[/\\])[^\s/\\]+", r"profiles/[REDACTED]", value)
        return value

    @staticmethod
    def _mapping(raw: object) -> Mapping[str, object]:
        if not isinstance(raw, Mapping):
            raise FeedbackValidationError("JSON object required")
        return raw

    @staticmethod
    def _string(payload: Mapping[str, object], field: str, default: str = "") -> str:
        value = payload.get(field, default)
        if value is None:
            return default
        if not isinstance(value, str):
            raise FeedbackValidationError(f"{field} must be a string")
        return value

    @classmethod
    def _limited_string(
        cls,
        payload: Mapping[str, object],
        field: str,
        limit: int,
        default: str = "",
    ) -> str:
        value = cls._string(payload, field, default).strip()
        if len(value) > limit:
            raise FeedbackValidationError(f"{field} is too long")
        return value or default

    @staticmethod
    def _category(raw: object) -> FeedbackCategory:
        try:
            return FeedbackCategory(raw)
        except (TypeError, ValueError):
            raise FeedbackValidationError("invalid_category") from None

    @staticmethod
    def _screenshot(raw: object) -> FeedbackScreenshot | None:
        if raw in (None, ""):
            return None
        if not isinstance(raw, str):
            raise FeedbackValidationError("invalid_screenshot")
        encoded = raw.strip()
        content_type = "image/png"
        if encoded.startswith("data:"):
            match = re.fullmatch(
                r"data:(image/(?:png|jpeg|webp));base64,(.*)",
                encoded,
                flags=re.DOTALL,
            )
            if match is None:
                raise FeedbackValidationError("invalid_screenshot")
            content_type, encoded = match.groups()
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise FeedbackValidationError("invalid_screenshot") from None
        if not content or len(content) > MAX_SCREENSHOT_BYTES:
            raise FeedbackValidationError("invalid_screenshot")
        return FeedbackScreenshot(content=content, content_type=content_type)
