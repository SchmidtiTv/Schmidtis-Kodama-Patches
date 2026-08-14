"""Serve bundled Composer application subpaths."""

from ... import blueprint
from .._files import composer_app

blueprint.route("/composer-app/<path:subpath>")(composer_app)
