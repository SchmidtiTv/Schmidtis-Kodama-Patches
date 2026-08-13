"""LAN remote control: a phone on the same network controls playback.

State bridges in-process — the app frontend pushes now-playing state and drains
the command queue; the phone reads state and enqueues commands. Access is gated
by a session token AND per-device desktop approval; the desktop-only control
operations are additionally restricted to localhost by the routes.
"""

import secrets
import time
from collections.abc import Mapping
from typing import TypedDict, cast

from src.config import BACKEND_PORT, PROJECT_ROOT


class Device(TypedDict):
    name: str
    status: str
    last_seen: float


class RemoteControl:
    """Owns remote-control enablement, the session token, trusted devices, the
    now-playing state mirror, and the pending-command queue.
    """

    def __init__(self) -> None:
        # Old server.py: _remote_enabled / _remote_token
        self.enabled: bool = False
        self.token: str | None = None
        # Old server.py: _remote_state
        self.state: dict[str, object] = {
            "title": "",
            "artists": "",
            "thumbnail": "",
            "isPlaying": False,
            "position": 0,
            "duration": 0,
            "hasTrack": False,
            "shuffle": False,
            "repeat": "none",
            "volume": 100,
            "isLiked": False,
            "queue": [],
        }
        self.cmds: list[dict[str, object]] = []
        self.devices: dict[str, Device] = {}
        self._ips_cache: dict[str, object] = {"ips": None, "ts": 0.0}
        self._html_cache: str | None = None

    def page_html(self) -> str:
        if self._html_cache is None:
            with open(PROJECT_ROOT / "static" / "remote.html", encoding="utf-8") as f:
                self._html_cache = f.read()
        return self._html_cache

    # Old server.py: _remote_local_ips
    def local_ips(self) -> list[str]:
        # Cached: the underlying getaddrinfo(hostname) can be slow/blocking on Windows and was
        # previously called on every _status poll (~2.5s). The LAN IP rarely changes.
        now = time.time()
        cached_ips = cast("list[str] | None", self._ips_cache["ips"])
        cached_at = cast("float", self._ips_cache["ts"])
        if cached_ips is not None and now - cached_at < 30:
            return cached_ips
        import socket

        ips: list[str] = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # no packets sent; just picks the primary iface
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = str(info[4][0])
                if ip not in ips and not ip.startswith("127."):
                    ips.append(ip)
        except Exception:
            pass
        self._ips_cache["ips"] = ips
        self._ips_cache["ts"] = now
        return ips

    # Old server.py: _remote_token_ok
    def token_ok(self, token: object) -> bool:
        return bool(self.enabled and self.token and token == self.token)

    # ── Desktop-only control operations ──
    # Old server.py: remote_enable
    def enable(self, data: Mapping[str, object]) -> dict[str, object]:
        enabled = bool(data.get("enabled"))
        self.enabled = enabled
        if enabled:
            # The desktop persists the token + trusted devices across restarts (backend state is
            # in-memory) and re-supplies them here, so old QR codes and remembered phones keep
            # working after a restart. A supplied token is reused; otherwise a fresh one is minted.
            supplied = str(data.get("token") or "").strip()
            if supplied:
                self.token = supplied[:64]
            elif not self.token:
                self.token = secrets.token_urlsafe(12)
            trusted = data.get("trusted")
            if isinstance(trusted, list):
                for tdev in trusted:
                    if not isinstance(tdev, dict):
                        continue
                    device = cast("dict[str, object]", tdev)
                    did = str(device.get("id") or "")
                    if did and did not in self.devices:
                        self.devices[did] = {
                            "name": str(device.get("name") or "Device")[:48],
                            "status": "approved",
                            "last_seen": 0,
                        }
        else:
            self.token = None
            self.devices = {}
            self.cmds = []
        return {
            "enabled": self.enabled,
            "token": self.token,
            "port": BACKEND_PORT,
            "ips": self.local_ips(),
        }

    # Old server.py: remote_status
    def status_payload(self) -> dict[str, object]:
        now = time.time()
        devices = [
            {
                "id": did,
                "name": d["name"],
                "status": d["status"],
                "online": (now - d.get("last_seen", 0)) < 12,
            }
            for did, d in self.devices.items()
        ]
        return {
            "enabled": self.enabled,
            "token": self.token,
            "port": BACKEND_PORT,
            "ips": self.local_ips(),
            "devices": devices,
        }

    # Old server.py: remote_device
    def device_action(self, data: Mapping[str, object]) -> tuple[dict[str, object], int]:
        did, action = str(data.get("id") or ""), str(data.get("action") or "")
        d = self.devices.get(did)
        if not d:
            return {"error": "unknown"}, 404
        if action == "approve":
            d["status"] = "approved"
        elif action in ("deny", "remove"):
            self.devices.pop(did, None)
        return {"ok": True}, 200

    # Old server.py: remote_push
    def push_state(self, data: Mapping[str, object]) -> None:
        self.state.update({k: v for k, v in (data or {}).items() if k in self.state})

    # Old server.py: remote_poll
    def poll(self) -> list[dict[str, object]]:
        cmds, self.cmds = self.cmds, []
        return cmds

    # Old server.py: remote_sync
    def sync(self, data: Mapping[str, object]) -> list[dict[str, object]]:
        """Combined push + poll — the app frontend sends now-playing state and
        receives any pending commands in one request.
        """
        st = (data or {}).get("state")
        if isinstance(st, dict):
            self.state.update({k: v for k, v in st.items() if k in self.state})
        cmds, self.cmds = self.cmds, []
        return cmds

    # ── Phone-facing operations (token + device-approval gated) ──
    # Old server.py: remote_hello
    def hello(self, data: Mapping[str, object]) -> tuple[dict[str, object], int]:
        if not self.token_ok(data.get("token")):
            return {"error": "invalid_token"}, 403
        did = str(data.get("deviceId") or "").strip()[:64]
        name = str(data.get("name") or "Device").strip()[:48] or "Device"
        if not did:
            return {"error": "no_device"}, 400
        d = self.devices.get(did)
        if not d:
            self.devices[did] = {"name": name, "status": "pending", "last_seen": time.time()}
        else:
            d["last_seen"], d["name"] = time.time(), name
        return {"status": self.devices[did]["status"]}, 200

    # Old server.py: remote_state
    def get_state(self, token: object, device_id: str | None) -> tuple[dict[str, object], int]:
        if not self.token_ok(token):
            return {"error": "invalid_token"}, 403
        d = self.devices.get(device_id or "")
        if not d:
            return {"status": "unknown"}, 200
        d["last_seen"] = time.time()
        if d["status"] != "approved":
            return {"status": d["status"]}, 200
        return {"status": "approved", "state": self.state}, 200

    # Old server.py: remote_cmd
    def command(self, data: Mapping[str, object]) -> tuple[dict[str, object], int]:
        if not self.token_ok(data.get("token")):
            return {"error": "invalid_token"}, 403
        d = self.devices.get(str(data.get("deviceId") or ""))
        if not d or d["status"] != "approved":
            return {"error": "not_allowed"}, 403
        d["last_seen"] = time.time()
        action = str(data.get("action") or "")
        if action in ("playpause", "next", "prev", "shuffle", "repeat", "like"):
            self.cmds.append({"action": action})
            return {"ok": True}, 200
        if action == "seek":
            position = data.get("position")
            if not isinstance(position, (int, float)):
                return {"error": "bad_position"}, 400
            self.cmds.append({"action": "seek", "position": position})
            return {"ok": True}, 200
        if action == "volume":
            value = data.get("value")
            if not isinstance(value, (int, float)):
                return {"error": "bad_value"}, 400
            self.cmds.append({"action": "volume", "value": value})
            return {"ok": True}, 200
        if action == "queueJump":
            video_id = data.get("videoId")
            if not isinstance(video_id, str) or not video_id:
                return {"error": "bad_video_id"}, 400
            self.cmds.append({"action": "queueJump", "videoId": video_id})
            return {"ok": True}, 200
        return {"error": "bad_action"}, 400
