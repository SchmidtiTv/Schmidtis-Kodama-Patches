import logging

from flask import Blueprint, Flask

from src.config import Config

from .auth import blueprint as auth_blueprint
from .cache import blueprint as cache_blueprint
from .clientlog import blueprint as clientlog_blueprint
from .composer import blueprint as composer_blueprint
from .discovery import blueprint as discovery_blueprint
from .downloads import blueprint as downloads_blueprint
from .feedback import blueprint as feedback_blueprint
from .lastFm import blueprint as lastfm_blueprint
from .library import blueprint as library_blueprint
from .lyrics import blueprint as lyrics_blueprint
from .news import blueprint as news_blueprint
from .operations import blueprint as operations_blueprint
from .profiles import blueprint as profiles_blueprint
from .root import blueprint as root_blueprint
from .streaming import blueprint as streaming_blueprint

logger = logging.getLogger(__name__)

# List of a Tuple with the blueprint and if debug
blueprints: list[tuple[Blueprint, bool]] = [
    (auth_blueprint, False),
    (news_blueprint, False),
    (clientlog_blueprint, True),
    (cache_blueprint, False),
    (composer_blueprint, False),
    (discovery_blueprint, False),
    (downloads_blueprint, False),
    (feedback_blueprint, False),
    (lastfm_blueprint, False),
    (library_blueprint, False),
    (lyrics_blueprint, False),
    (operations_blueprint, False),
    (profiles_blueprint, False),
    (root_blueprint, False),
    (streaming_blueprint, False),
]


def register_blueprints(application: Flask) -> None:
    try:
        for bp in blueprints:
            blueprint, is_debug = bp

            if is_debug and not Config.DEBUG:
                continue
            if Config.DEBUG:
                logger.debug("Registering blueprint: %s", blueprint.name)

            application.register_blueprint(blueprint)
    except Exception as error:
        raise RuntimeError("Failed to register application blueprints.") from error
