"""Music-library, playlist, album, artist, radio, and song-detail endpoints."""

from flask import Blueprint

blueprint = Blueprint("library", __name__)

from . import album, artist, history, library, mix, playlist, radio, song
