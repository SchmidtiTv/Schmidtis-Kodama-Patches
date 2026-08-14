"""Request-local checks shared by desktop remote-control routes."""

from flask import request


def _is_local() -> bool:
    remote_address = request.remote_addr or ""
    return remote_address.startswith("127.") or remote_address in ("::1", "localhost")
