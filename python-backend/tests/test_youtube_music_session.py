import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from src.lib.music.playlist import Playlist
from src.lib.music.youtube_music import YoutubeMusicSession
from ytmusicapi.exceptions import YTMusicServerError


class YoutubeMusicSessionTests:
    def test_verification_retries_transient_first_call_rejection(self) -> None:
        # A just-switched (e.g. brand-account) session can reject its first InnerTube
        # call with HTTP 400 until its cookies settle; the login must survive that.
        session = YoutubeMusicSession(profiles=MagicMock())
        client = MagicMock()
        client.get_liked_songs.side_effect = [YTMusicServerError("HTTP 400"), {"tracks": []}]

        with (
            patch.object(session, "create_client", return_value=client),
            patch("src.lib.music.youtube_music.time.sleep") as sleep,
            patch("src.lib.music.youtube_music.threading.Thread"),
        ):
            assert session.activate_verified_profile("brand") is client

        assert client.get_liked_songs.call_count == 2
        sleep.assert_called_once_with(session.VERIFY_BACKOFF_SECONDS)
        assert session.state.current_profile == "brand"

    def test_verification_reraises_after_exhausting_retries(self) -> None:
        session = YoutubeMusicSession(profiles=MagicMock())
        client = MagicMock()
        client.get_liked_songs.side_effect = YTMusicServerError("HTTP 400")

        with (
            patch.object(session, "create_client", return_value=client),
            patch("src.lib.music.youtube_music.time.sleep"),
            patch("src.lib.music.youtube_music.threading.Thread"),
            pytest.raises(YTMusicServerError),
        ):
            session.activate_verified_profile("brand")

        assert client.get_liked_songs.call_count == session.VERIFY_ATTEMPTS
        assert session.state.ytm is None

    def test_create_client_passes_profile_path_as_string(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "google.headers.json"
            path.write_text(json.dumps({"authorization": "SAPISIDHASH test"}), encoding="utf-8")
            profiles = MagicMock()
            profiles.profile_file_path.return_value = path
            client_factory = MagicMock()
            session = YoutubeMusicSession(profiles=profiles, client_factory=client_factory)

            session.create_client("google")

        client_factory.assert_called_once_with(str(path), user=profiles.brand_user_id.return_value)

    def test_system_client_is_anonymous_and_reused(self) -> None:
        client_factory = MagicMock()
        session = YoutubeMusicSession(profiles=MagicMock(), client_factory=client_factory)

        first = session.get_system_client()
        second = session.get_system_client()

        assert first is second
        client_factory.assert_called_once_with()

    def test_cookie_refresh_loop_starts_only_once_per_session(self) -> None:
        session = YoutubeMusicSession(profiles=MagicMock())

        with patch("src.lib.music.youtube_music.threading.Thread") as thread_class:
            assert session.start_cookie_refresh_loop()
            assert not session.start_cookie_refresh_loop()

        thread_class.assert_called_once_with(
            target=session.run_cookie_refresh_loop,
            name="youtube-cookie-refresh",
            daemon=True,
        )
        thread_class.return_value.start.assert_called_once_with()

    def test_reauth_and_logout_clear_only_that_profiles_playlist_memory(self) -> None:
        playlist_cache = MagicMock()
        session = YoutubeMusicSession(profiles=MagicMock(), playlist_cache=playlist_cache)
        client = MagicMock()

        with (
            patch.object(session, "create_client", return_value=client),
            patch("src.lib.music.youtube_music.threading.Thread"),
        ):
            assert session.activate_verified_profile("default") is client

        session.clear_active_profile()

        assert playlist_cache.clear_memory_for_profile.call_args_list == [
            call("default"),
            call("default"),
        ]

    def test_profile_memory_clear_preserves_other_profiles_entries(self) -> None:
        playlist_cache = Playlist()
        playlist_cache.put("LM", "default", {"tracks": ["old"]})
        playlist_cache.put("LM", "second", {"tracks": ["other"]})

        playlist_cache.clear_memory_for_profile("default")

        assert playlist_cache.get_memory("LM", "default") is None
        assert playlist_cache.get_memory("LM", "second") == {"tracks": ["other"]}

    def test_autoload_prefers_the_last_active_profile(self) -> None:
        profiles = MagicMock()
        profiles.load_active_profile.return_value = "second"
        profiles.list_profiles.return_value = [
            {"name": "first"},
            {"name": "second"},
        ]
        session = YoutubeMusicSession(profiles=profiles)

        with (
            patch.object(session, "activate_profile", return_value=True) as activate,
            patch("src.lib.music.youtube_music.threading.Thread"),
        ):
            session.autoload_first_profile()

        activate.assert_called_once_with("second")
