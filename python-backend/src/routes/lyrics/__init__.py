"""Lyrics and Unison endpoints."""

from flask import Blueprint

blueprint = Blueprint("lyrics", __name__)

from . import lyrics, romanize_lyrics, translate_lyrics, unison
