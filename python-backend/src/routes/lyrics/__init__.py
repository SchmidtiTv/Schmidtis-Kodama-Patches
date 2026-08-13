"""Lyrics and Unison endpoints."""

from flask import Blueprint

blueprint = Blueprint("lyrics", __name__)

from . import (
    custom_delete,
    custom_get,
    custom_save,
    get,
    romanize,
    translate,
    unison_displayname,
    unison_nickname,
    unison_nickname_check,
    unison_report,
    unison_versions,
    unison_vote,
)
