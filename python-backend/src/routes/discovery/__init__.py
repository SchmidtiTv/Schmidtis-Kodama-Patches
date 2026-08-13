"""Podcast and mood/genre discovery endpoints."""

from flask import Blueprint

blueprint = Blueprint("discovery", __name__)

from . import mood, podcast
