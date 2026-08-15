"""Validated values passed to the feedback webhook integration."""

from dataclasses import dataclass, field
from enum import StrEnum


class FeedbackCategory(StrEnum):
    BUG = "Bug"
    CRASH = "Absturz"
    DESIGN = "UI / Design"
    SUGGESTION = "Vorschlag"


@dataclass(frozen=True, slots=True)
class FeedbackScreenshot:
    content: bytes = field(repr=False)
    content_type: str


@dataclass(frozen=True, slots=True)
class FeedbackSubmission:
    title: str
    category: FeedbackCategory
    severity: str
    description: str
    application_version: str
    operating_system: str
    reporter: str
    include_logs: bool
    screenshot: FeedbackScreenshot | None
    diagnostic_logs: bytes | None = field(default=None, repr=False, compare=False)
