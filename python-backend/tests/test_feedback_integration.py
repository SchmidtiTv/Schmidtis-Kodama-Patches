import base64

import pytest
from src.lib.feedback import (
    FeedbackCategory,
    FeedbackNotConfiguredError,
    FeedbackService,
    FeedbackSubmission,
    FeedbackValidationError,
)
from src.lib.feedback.models import FeedbackScreenshot
from src.lib.feedback.service import MAX_LOG_BYTES, MAX_SCREENSHOT_BYTES
from src.lib.integrations.feedback_webhook import DiscordFeedbackWebhookClient
from src.lib.integrations.http import HttpTransportTimeout
from src.lib.providers import (
    ProviderAuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)

from http_test_support import FakeHttpResponse, RecordingHttpTransport


class RecordingFeedbackClient:
    def __init__(self) -> None:
        self.submissions: list[FeedbackSubmission] = []

    def submit(self, submission: FeedbackSubmission) -> None:
        self.submissions.append(submission)


def _submission(screenshot: FeedbackScreenshot | None = None) -> FeedbackSubmission:
    return FeedbackSubmission(
        title="Title",
        category=FeedbackCategory.BUG,
        severity="High",
        description="Description",
        application_version="1.0",
        operating_system="Linux",
        reporter="Reporter",
        include_logs=False,
        screenshot=screenshot,
    )


class DiscordFeedbackWebhookClientTests:
    def test_json_submission_has_fixed_provider_format_and_timeout(self) -> None:
        response = FakeHttpResponse(status_code=204)
        http = RecordingHttpTransport(response)
        client = DiscordFeedbackWebhookClient(http, "https://discord.com/api/webhooks/id/token")

        client.submit(_submission())

        call = http.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == "https://discord.com/api/webhooks/id/token"
        assert call["timeout"] == (4.0, 8.0)
        assert call["allow_redirects"] is False
        assert "json" in call and "files" not in call
        assert response.closed

    def test_screenshot_uses_multipart_with_a_fixed_attachment_name(self) -> None:
        http = RecordingHttpTransport(FakeHttpResponse(status_code=200))
        client = DiscordFeedbackWebhookClient(http, "https://example.com/hooks/feedback")

        client.submit(_submission(FeedbackScreenshot(b"png", "image/png")))

        call = http.calls[0]
        files = call["files"]
        assert isinstance(files, dict)
        assert files["file_shot"] == ("screenshot.png", b"png", "image/png")
        assert call["timeout"] == (4.0, 11.0)
        assert "data" in call and "json" not in call

    @pytest.mark.parametrize(
        ("status", "error_type"),
        [(401, ProviderAuthenticationError), (400, ProviderResponseError)],
    )
    def test_provider_statuses_become_safe_errors(
        self, status: int, error_type: type[Exception]
    ) -> None:
        secret_url = "https://discord.com/api/webhooks/private/token"
        client = DiscordFeedbackWebhookClient(
            RecordingHttpTransport(FakeHttpResponse(status_code=status)),
            secret_url,
        )

        with pytest.raises(error_type) as raised:
            client.submit(_submission())

        assert secret_url not in str(raised.value)

    def test_timeout_becomes_safe_unavailable_error(self) -> None:
        secret_url = "https://discord.com/api/webhooks/private/token"
        client = DiscordFeedbackWebhookClient(
            RecordingHttpTransport(error=HttpTransportTimeout(secret_url)),
            secret_url,
        )

        with pytest.raises(ProviderUnavailableError) as raised:
            client.submit(_submission())

        assert secret_url not in str(raised.value)


class FeedbackServiceTests:
    def test_missing_configuration_preserves_not_configured_behavior(self) -> None:
        service = FeedbackService(None, lambda: [])

        with pytest.raises(FeedbackNotConfiguredError):
            service.submit({"title": "Feedback"})

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"title": "ok", "category": "unknown"},
            {"title": 123},
            {"title": "ok", "includeLogs": "yes"},
        ],
    )
    def test_invalid_categories_and_required_fields_are_rejected(self, payload: object) -> None:
        service = FeedbackService(RecordingFeedbackClient(), lambda: [])

        with pytest.raises(FeedbackValidationError):
            service.submit(payload)

    def test_screenshot_size_and_encoding_are_enforced(self) -> None:
        service = FeedbackService(RecordingFeedbackClient(), lambda: [])
        too_large = base64.b64encode(b"x" * (MAX_SCREENSHOT_BYTES + 1)).decode()

        with pytest.raises(FeedbackValidationError):
            service.submit({"title": "ok", "screenshot": too_large})
        with pytest.raises(FeedbackValidationError):
            service.submit({"title": "ok", "screenshot": "not base64!"})

    def test_logs_are_bounded_and_sensitive_values_are_redacted(self) -> None:
        client = RecordingFeedbackClient()
        webhook = "https://discord.com/api/webhooks/123/private-token"
        logs = [
            "Authorization: bearer-secret Cookie=session-secret token=raw-secret",
            f"failed request {webhook}",
            "database profiles/alice/private.db",
            "x" * (MAX_LOG_BYTES + 100),
        ]
        service = FeedbackService(client, lambda: logs)

        service.submit({"title": "ok", "includeLogs": True})

        encoded = client.submissions[0].diagnostic_logs
        assert encoded is not None
        assert len(encoded) <= MAX_LOG_BYTES
        decoded = encoded.decode("utf-8")
        assert "bearer-secret" not in decoded
        assert "session-secret" not in decoded
        assert "raw-secret" not in decoded
        assert webhook not in decoded
        assert "profiles/alice" not in decoded
