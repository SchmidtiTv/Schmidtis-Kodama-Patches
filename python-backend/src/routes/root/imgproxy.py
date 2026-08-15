"""HTTP adapter for restricted, cached image proxy retrieval."""

from flask import Response, current_app, jsonify, request

from src.lib.integrations.image_proxy import ImageTargetRejectedError
from src.lib.providers import ProviderError
from src.type_defs import RouteResponse

from . import blueprint
from ._services import image_proxy_service


@blueprint.route("/imgproxy")
def img_proxy() -> RouteResponse:
    url = request.args.get("url", "")
    if not url:
        return "", 400
    try:
        result = image_proxy_service().fetch(
            url,
            high_quality=request.args.get("hq", "0") == "1",
        )
        response = Response(result.image.content, content_type=result.image.content_type)
        response.headers["Cache-Control"] = result.image.cache_control or "public, max-age=604800"
        response.headers["X-Cache"] = "HIT" if result.cache_hit else "MISS"
        return response
    except ImageTargetRejectedError:
        return jsonify({"error": "image_target_forbidden"}), 403
    except ValueError:
        return jsonify({"error": "invalid_image_url"}), 400
    except ProviderError:
        return jsonify({"error": "image_unavailable"}), 502
    except Exception:
        current_app.logger.exception("Unexpected image proxy failure")
        return jsonify({"error": "image_unavailable"}), 500
