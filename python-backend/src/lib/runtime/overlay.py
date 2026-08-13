"""OBS overlay: now-playing state, the v2 document schema, and a second WSGI
server so OBS can hold a long-lived SSE connection independent of the main app.

The v1→v2 migration mirrors ``src/overlay/schema.js`` in the frontend.
"""

import contextlib
import json
import logging
import queue
import threading
from collections.abc import Generator, Mapping

from flask import Flask, Response, jsonify
from flask_cors import CORS
from werkzeug.serving import BaseWSGIServer
from werkzeug.serving import make_server as _make_wsgi_server

from src.config import PROJECT_ROOT, config_overlay


# ── v2 document schema / migration helpers ───────────────────────────────────
def _r(v: float) -> int:
    return int(v + 0.5)  # round-half-up for non-negative (mirrors JS Math.round)


def _make_id(prefix: str = "l") -> str:
    import random as _rnd
    import time as _t

    return f"{prefix}_{int(_t.time() * 1000) & 0xFFFFFFFF:x}{_rnd.randint(0, 0xFFFF):x}"


def _uniform_corners(radius: float = 14, t: str = "r") -> dict[str, object]:
    return {
        "TL": radius,
        "TR": radius,
        "BR": radius,
        "BL": radius,
        "typeTL": t,
        "typeTR": t,
        "typeBR": t,
        "typeBL": t,
    }


def _corners_from_v1(
    cfg: Mapping[str, object], rk: list[str], tk: list[str], fb: object
) -> dict[str, object]:
    return {
        "TL": cfg.get(rk[0], fb),
        "TR": cfg.get(rk[1], fb),
        "BR": cfg.get(rk[2], fb),
        "BL": cfg.get(rk[3], fb),
        "typeTL": cfg.get(tk[0]) or "r",
        "typeTR": cfg.get(tk[1]) or "r",
        "typeBR": cfg.get(tk[2]) or "r",
        "typeBL": cfg.get(tk[3]) or "r",
    }


def _base_layer(type_: str, over: dict[str, object]) -> dict[str, object]:
    layer: dict[str, object] = {
        "id": _make_id(type_[:3]),
        "type": type_,
        "name": over.get("name", type_),
        "x": 0,
        "y": 0,
        "w": 100,
        "h": 40,
        "rotation": 0,
        "opacity": 100,
        "z": 0,
        "visible": True,
        "locked": False,
        "bind": None,
        "style": {},
        "effects": [],
    }
    layer.update(over)
    return layer


def _default_canvas(over: dict[str, object] | None = None) -> dict[str, object]:
    c: dict[str, object] = {
        "width": 400,
        "height": 80,
        "autoSize": False,
        "bg": {"color": "#1a1a1a", "opacity": 90, "blurFromCover": False, "blur": 10},
        "corners": _uniform_corners(14, "r"),
        "border": {"on": False, "color": "#EEA8FF", "width": 1.5, "glow": 0},
        "shadow": {"on": False, "strength": 0.35},
        "autoHide": False,
        "theme": {
            "fontFamily": "system-ui, sans-serif",
            "textColor": "#ffffff",
            "accentColor": "#EEA8FF",
        },
    }
    if over:
        c.update(over)
    return c


def _number(value: object, default: float) -> float:
    return (
        float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
    )


def _string(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _enabled(value: object, default: bool = True) -> bool:
    return value if isinstance(value, bool) else default


def migrate_v1_to_v2(cfg: Mapping[str, object] | None) -> dict[str, object]:
    """Accepts a flat v1 config OR a v2 doc (passthrough). Returns a v2 doc."""
    cfg = cfg or {}
    if (
        cfg.get("version") == config_overlay.DOCUMENT_VERSION
        and isinstance(cfg.get("layers"), list)
        and cfg.get("canvas")
    ):
        return dict(cfg)
    g = cfg.get
    padH = _number(g("paddingH"), 16)
    padV = _number(g("paddingV"), 12)
    gap = _number(g("gap"), 12)
    artSize = _number(g("artSize"), 56)
    showArt = _enabled(g("showAlbumArt"))
    showProgress = _enabled(g("showProgress"))
    progH = _number(g("progressHeight"), 3)
    titleFS = _number(g("titleFontSize"), 14)
    subFS = _number(g("artistFontSize"), 12)
    textColor = _string(g("textColor"), "#ffffff")
    accentColor = _string(g("accentColor"), "#EEA8FF")
    fontFamily = _string(g("fontFamily"), "system-ui, sans-serif")
    W = _number(g("widgetWidth"), 400)
    titleLineH = _r(titleFS * 1.3)
    subLineH = _r(subFS * 1.3)
    textBlockH = titleLineH + 3 + subLineH
    rowH = max(artSize if showArt else 0, textBlockH)
    wh = _number(g("widgetHeight"), 0)
    H = wh if (wh and wh > 0) else _r(padV * 2 + rowH)
    contentX = padH + (artSize + gap if showArt else 0)
    contentW = max(10, W - contentX - padH)
    textY = _r((H - textBlockH) / 2)
    canvas = _default_canvas(
        {
            "width": W,
            "height": H,
            "autoSize": _enabled(g("dynamicWidth"), False),
            "bg": {
                "color": _string(g("bgColor"), "#1a1a1a"),
                "opacity": _number(g("bgOpacity"), 90),
                "blurFromCover": _enabled(g("bgBlurEnabled"), False),
                "blur": _number(g("bgBlur"), 10),
            },
            "corners": _corners_from_v1(
                cfg,
                ["radiusTL", "radiusTR", "radiusBR", "radiusBL"],
                ["cornerTypeTL", "cornerTypeTR", "cornerTypeBR", "cornerTypeBL"],
                _number(g("borderRadius"), 14),
            ),
            "border": {
                "on": _enabled(g("border"), False),
                "color": _string(g("borderColor"), "#EEA8FF"),
                "width": _number(g("borderWidth"), 1.5),
                "glow": _number(g("borderBlur"), 0),
            },
            "shadow": {
                "on": _enabled(g("showShadow"), False),
                "strength": _number(g("shadowStrength"), 0.35),
            },
            "autoHide": _enabled(g("autoHide"), False),
            "theme": {"fontFamily": fontFamily, "textColor": textColor, "accentColor": accentColor},
        }
    )
    layers = []
    z = 0
    if showArt:
        layers.append(
            _base_layer(
                "albumArt",
                {
                    "name": "Album Art",
                    "x": padH,
                    "y": _r((H - artSize) / 2),
                    "w": artSize,
                    "h": artSize,
                    "z": z,
                    "bind": "cover",
                    "style": {
                        "corners": _corners_from_v1(
                            cfg,
                            ["artRadiusTL", "artRadiusTR", "artRadiusBR", "artRadiusBL"],
                            [
                                "artCornerTypeTL",
                                "artCornerTypeTR",
                                "artCornerTypeBR",
                                "artCornerTypeBL",
                            ],
                            _number(g("artRadius"), 8),
                        ),
                        "fit": "cover",
                        "border": {"on": False, "color": "#EEA8FF", "width": 1.5},
                        "shadow": {"on": False, "strength": 0.35},
                        "placeholderBg": "rgba(255,255,255,0.12)",
                    },
                },
            )
        )
        z += 1
    layers.append(
        _base_layer(
            "text",
            {
                "name": "Title",
                "x": contentX,
                "y": textY,
                "w": contentW,
                "h": titleLineH,
                "z": z,
                "bind": "title",
                "style": {
                    "content": "",
                    "parts": [],
                    "fontFamily": fontFamily,
                    "fontSize": titleFS,
                    "fontWeight": 700,
                    "color": textColor,
                    "align": "left",
                    "valign": "top",
                    "letterSpacing": 0,
                    "lineHeight": 1.3,
                    "maxLines": 1,
                    "marquee": _enabled(g("scrollTitle"), False),
                    "marqueeSpeed": _number(g("scrollSpeed"), 80),
                },
            },
        )
    )
    z += 1
    parts = []
    if _enabled(g("showArtist")):
        parts.append("artist")
    if _enabled(g("showAlbum"), False):
        parts.append("album")
    layers.append(
        _base_layer(
            "text",
            {
                "name": "Subtitle",
                "x": contentX,
                "y": textY + titleLineH + 3,
                "w": contentW,
                "h": subLineH,
                "z": z,
                "opacity": 65,
                "bind": "subtitle",
                "style": {
                    "content": "",
                    "parts": parts,
                    "fontFamily": fontFamily,
                    "fontSize": subFS,
                    "fontWeight": 400,
                    "color": textColor,
                    "align": "left",
                    "valign": "top",
                    "letterSpacing": 0,
                    "lineHeight": 1.3,
                    "maxLines": 1,
                    "marquee": False,
                    "marqueeSpeed": 80,
                },
            },
        )
    )
    z += 1
    if showProgress:
        layers.append(
            _base_layer(
                "progress",
                {
                    "name": "Progress",
                    "x": 0,
                    "y": H - progH,
                    "w": W,
                    "h": progH,
                    "z": z,
                    "bind": "progress",
                    "style": {
                        "fillColor": accentColor,
                        "trackColor": "rgba(255,255,255,0.12)",
                        "corners": _uniform_corners(0, "r"),
                        "shape": "bar",
                    },
                },
            )
        )
        z += 1
    return {"version": config_overlay.DOCUMENT_VERSION, "canvas": canvas, "layers": layers}


class OverlayServer:
    """Owns the overlay document/state and the optional OBS-facing WSGI server."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger: logging.Logger = logger or logging.getLogger(__name__)
        # Old server.py: _ov_state
        self._state: dict[str, object] = {
            "title": "",
            "artist": "",
            "album": "",
            "cover": "",
            "progress": 0.0,
            "duration": 0.0,
            "isPlaying": False,
        }
        # Old server.py: _ov_doc — the frontend may POST v1 configs → migrated on arrival.
        self._doc = migrate_v1_to_v2(config_overlay.V1_DEFAULT)
        self._clients: list[queue.Queue[str]] = []
        self._lock = threading.Lock()
        self._server_obj: BaseWSGIServer | None = None
        self._server_thread: threading.Thread | None = None
        self._html_cache: str | None = None
        self._app = self._build_overlay_app()

    # ── Widget HTML (lazy so a missing file only breaks the page, not startup) ─
    def _overlay_html(self) -> str:
        if self._html_cache is None:
            with open(PROJECT_ROOT / "static" / "overlay.html", encoding="utf-8") as f:
                self._html_cache = f.read()
        return self._html_cache

    # Second WSGI app registered with the shared overlay handlers, so OBS keeps
    # working even when the main app is busy.
    def _build_overlay_app(self) -> Flask:
        overlay_app = Flask("kiyoshi_overlay")
        CORS(overlay_app)
        overlay_app.add_url_rule("/overlay", "overlay_page", self.page_response)
        overlay_app.add_url_rule("/overlay/config", "overlay_config", lambda: jsonify(self._doc))
        overlay_app.add_url_rule("/overlay/stream", "overlay_stream", self.stream_response)
        return overlay_app

    # Old server.py: _ov_push
    def push(self, payload: dict[str, object]) -> None:
        msg = "data: " + json.dumps(payload) + "\n\n"
        with self._lock:
            dead = []
            for q in self._clients:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                with contextlib.suppress(ValueError):
                    self._clients.remove(q)

    # Old server.py: _ov_page_resp
    def page_response(self) -> Response:
        resp = Response(self._overlay_html(), content_type="text/html; charset=utf-8")
        resp.headers["X-Frame-Options"] = "ALLOWALL"
        resp.headers["Content-Security-Policy"] = "frame-ancestors *"
        resp.headers["Access-Control-Allow-Origin"] = "*"
        # No-cache so OBS/CEF (and the editor iframe) always load the latest engine
        # after an update instead of a stale cached page.
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    # Old server.py: _ov_stream_resp
    def stream_response(self) -> Response:
        q = queue.Queue(maxsize=30)
        with self._lock:
            self._clients.append(q)
        initial = "data: " + json.dumps({**self._state, "_config": self._doc}) + "\n\n"

        def _gen() -> Generator[str, None, None]:
            try:
                yield initial
                while True:
                    try:
                        yield q.get(timeout=25)
                    except queue.Empty:
                        yield ": ping\n\n"
            finally:
                with self._lock, contextlib.suppress(ValueError):
                    self._clients.remove(q)

        return Response(
            _gen(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )

    def get_config(self) -> dict[str, object]:
        return self._doc

    # Old server.py: overlay_config (POST branch)
    def set_config(self, cfg: dict[str, object] | None) -> dict[str, object]:
        self._doc = migrate_v1_to_v2(cfg or {})
        self.push({"_configUpdate": True, "config": self._doc})
        return self._doc

    # Old server.py: overlay_push
    def update_state(self, data: dict[str, object] | None) -> None:
        self._state.update({k: v for k, v in (data or {}).items() if k in self._state})
        self.push(self._state)

    # Old server.py: _ov_start
    def start(self, port: int) -> bool:
        self.stop()
        try:
            # threaded=True is essential: OBS holds a long-lived SSE connection on
            # /overlay/stream. A single-threaded server would then be unable to serve
            # the page itself (reloads hang), leaving OBS stuck on a stale page.
            srv = _make_wsgi_server("0.0.0.0", port, self._app, threaded=True)
            self._server_obj = srv

            def _serve_safe() -> None:
                try:
                    srv.serve_forever()
                except Exception as e:
                    self._logger.error(f"[Overlay] Server thread died unexpectedly: {e}")

            t = threading.Thread(target=_serve_safe, daemon=True, name="kiyoshi-overlay")
            t.start()
            self._server_thread = t
            return True
        except OSError as e:
            print(f"[Overlay] Port {port} unavailable: {e}")
            return False

    # Old server.py: _ov_stop
    def stop(self) -> None:
        if self._server_obj:
            with contextlib.suppress(Exception):
                self._server_obj.shutdown()
            self._server_obj = None
        self._server_thread = None

    # Old server.py: overlay_status
    def status(self) -> dict[str, bool | int]:
        return {"running": self._server_obj is not None, "clients": len(self._clients)}
