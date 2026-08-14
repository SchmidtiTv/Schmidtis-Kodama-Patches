"""Serve the bundled Composer application root."""

from .. import blueprint
from ._files import composer_app

blueprint.route("/composer-app/", defaults={"subpath": ""})(composer_app)
