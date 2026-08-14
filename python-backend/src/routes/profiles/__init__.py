from flask import Blueprint

blueprint = Blueprint("profiles", __name__, url_prefix="/profiles")

from . import avatar, delete, index, rename, switch
