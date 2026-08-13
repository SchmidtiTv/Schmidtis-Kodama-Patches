from flask import Blueprint, request

blueprint = Blueprint("clientlog", __name__)


@blueprint.route("/clientlog", methods=["POST", "OPTIONS"])
def clientlog() -> tuple[str, int]:
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        msg = request.get_data(as_text=True)
    except Exception:
        msg = "<unreadable>"
    print(f"[client] {msg}", flush=True)
    return ("", 204)
