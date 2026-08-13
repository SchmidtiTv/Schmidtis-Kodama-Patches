"""Authentication and profile-session routes."""

from flask import Blueprint

blueprint = Blueprint("auth", __name__, url_prefix="/auth")

from . import (
    begin_add,
    cookie_login,
    end_add,
    local_create,
    logout,
    refresh_cookies,
    setup,
    validate,
)
