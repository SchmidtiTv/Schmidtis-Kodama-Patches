"""Security tests for yt-dlp cookie handling."""

import io
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import yt_dlp

from src.lib.integrations.ytdlp import YTDLP


class CookieStorageTests:
    """Ensure yt-dlp cookies remain in memory and legacy files are removed."""

    def test_authenticated_cookies_use_an_in_memory_stream(self) -> None:
        """Never create a per-profile Netscape cookie file."""
        with tempfile.TemporaryDirectory() as directory:
            profiles_dir = Path(directory)
            profile_path = profiles_dir / "default.json"
            profile_path.write_text(json.dumps({"cookie": "SID=profile"}), encoding="utf-8")
            legacy_cookie_file = profiles_dir / "default_ydl_cookies.txt"
            legacy_cookie_file.write_text("plaintext", encoding="utf-8")

            profiles = MagicMock()
            profiles.directory = profiles_dir
            profiles.is_local.return_value = False
            profiles.profile_file_path.return_value = profile_path
            session_cookie = SimpleNamespace(
                domain=".youtube.com",
                name="__Secure-PSID",
                value="session",
            )
            session = SimpleNamespace(cookies=[session_cookie])
            state = SimpleNamespace(
                current_profile="default",
                ytm=SimpleNamespace(_session=session),
            )

            ytdlp = YTDLP(profiles=profiles, music_state=state)
            ytdlp.last_cookie_refresh = time.time()
            options: dict[str, object] = {}

            ytdlp.apply_active_session_auth(options)

            cookie_stream = options["cookiefile"]
            assert isinstance(cookie_stream, io.StringIO)
            cookie_text = cookie_stream.getvalue()
            assert "SID\tprofile" in cookie_text
            assert "__Secure-PSID\tsession" in cookie_text
            cookie_stream.seek(0)
            with yt_dlp.YoutubeDL({"cookiefile": cookie_stream, "quiet": True}) as downloader:
                cookie_names = {cookie.name for cookie in downloader.cookiejar}
            assert {"SID", "__Secure-PSID"} <= cookie_names
            assert not legacy_cookie_file.exists()
            assert not list(profiles_dir.glob("*_ydl_cookies.txt"))
