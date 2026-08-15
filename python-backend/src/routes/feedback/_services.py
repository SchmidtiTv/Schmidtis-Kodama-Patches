from typing import cast

from flask import current_app

from src.lib.feedback import FeedbackService


def feedback_service() -> FeedbackService:
    return cast("FeedbackService", current_app.extensions["feedback_service"])
