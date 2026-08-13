"""Shared access to the Composer Bridge service."""

from typing import cast

from flask import current_app

from src.lib.composer.bridge import ComposerBridge


def composer_bridge() -> ComposerBridge:
    return cast("ComposerBridge", current_app.extensions["composer_bridge"])
