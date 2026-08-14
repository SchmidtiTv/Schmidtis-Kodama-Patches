"""Standalone top-level API endpoints."""

from flask import Blueprint

blueprint = Blueprint("root", __name__)

from . import artist_albums, home, imgproxy, like, liked, search, shutdown, status
