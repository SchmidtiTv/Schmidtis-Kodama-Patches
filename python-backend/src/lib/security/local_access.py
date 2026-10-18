"""Request guard for the local backend.

The backend listens on every interface so a phone on the LAN can use remote control, which
also exposes it to the rest of the network and to web pages open in the user's browser. This
guard narrows that surface: the Host header must name this machine (DNS rebinding), other
machines may only reach the phone-facing remote-control routes, and a state-changing request
from a browser must come from the app itself or the page the backend served.
"""

import ipaddress

from flask import Flask, Response, jsonify, request

APP_ORIGINS = (
    "http://localhost:1421",  # Tauri dev server
    "http://127.0.0.1:1421",  # Tauri dev server, by address
    "tauri://localhost",  # Tauri production (macOS/Linux)
    "https://tauri.localhost",  # Tauri production (Tauri 2.x, WebView2)
    "http://tauri.localhost",  # fallback
    "http://localhost",
    "http://127.0.0.1",
)

LAN_ROUTES = frozenset({"/remote", "/remote/hello", "/remote/state", "/remote/cmd"})

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        address = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def is_loopback_address(remote_addr: str | None) -> bool:
    address = _ip(remote_addr or "")
    return bool(address and address.is_loopback)


def is_trusted_host(host: str) -> bool:
    """Only this machine's names and IP literals; a rebinding attack needs a domain name."""
    hostname = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    if hostname.startswith("[") and "]" in hostname:
        hostname = hostname[1 : hostname.index("]")]
    hostname = hostname.lower()
    return hostname == "localhost" or _ip(hostname) is not None


def is_trusted_origin(origin: str, host_url: str) -> bool:
    return origin in APP_ORIGINS or origin == host_url.rstrip("/")


def _forbidden(reason: str) -> tuple[Response, int]:
    return jsonify({"error": "forbidden", "reason": reason}), 403


def _guard() -> tuple[Response, int] | None:
    if not is_trusted_host(request.host):
        return _forbidden("host")
    if not is_loopback_address(request.remote_addr) and request.path not in LAN_ROUTES:
        return _forbidden("lan")
    origin = request.headers.get("Origin")
    if (
        request.method in _UNSAFE_METHODS
        and origin
        and not is_trusted_origin(origin, request.host_url)
    ):
        return _forbidden("origin")
    return None


def install_local_access_guard(app: Flask) -> None:
    app.before_request(_guard)
