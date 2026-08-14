"""Local Composer Bridge and bundled Composer app endpoints."""

from flask import Blueprint

blueprint = Blueprint("composer", __name__)

from . import composer_app, composer_bridge
