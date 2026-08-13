"""Configuration lookup for the optional feedback webhook."""

import json
import os
import sys
from pathlib import Path

from src.config import PROJECT_ROOT


def load_feedback_webhook() -> str:
    """Load the webhook from the environment or the packaged/local config file."""
    webhook = os.environ.get("KODAMA_FEEDBACK_WEBHOOK", "").strip()
    if webhook:
        return webhook

    candidates = []
    bundle_root = vars(sys).get("_MEIPASS")
    if getattr(sys, "frozen", False) and isinstance(bundle_root, str):
        candidates.append(Path(bundle_root) / "feedback_config.json")
    candidates.append(PROJECT_ROOT / "feedback_config.json")

    for path in candidates:
        try:
            with path.open(encoding="utf-8") as config_file:
                return (json.load(config_file).get("webhook") or "").strip()
        except (OSError, ValueError, TypeError):
            continue
    return ""
