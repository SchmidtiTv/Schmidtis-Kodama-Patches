"""Operations and integrations: debug info, OBS overlay, LAN remote, and fonts."""

from flask import Blueprint

blueprint = Blueprint("operations", __name__)

from . import api, debug, network, overlay, remote
