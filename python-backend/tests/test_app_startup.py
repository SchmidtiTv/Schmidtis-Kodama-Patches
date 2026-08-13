from contextlib import ExitStack
from unittest.mock import MagicMock, call, patch

from src import create_app


class AppStartupTests:
    def test_app_startup_restores_a_saved_profile(self) -> None:
        startup_steps = []
        with ExitStack() as patches:
            patches.enter_context(patch("src.NetworkSettings"))
            load_feedback_webhook = patches.enter_context(
                patch("src.load_feedback_webhook", return_value="https://hooks.example.test")
            )
            profile_class = patches.enter_context(patch("src.Profile"))
            session_class = patches.enter_context(patch("src.YoutubeMusicSession"))
            patches.enter_context(patch("src.LastFM"))
            patches.enter_context(patch("src.CacheSettings"))
            patches.enter_context(patch("src.MetadataCache"))
            patches.enter_context(patch("src.ComposerBridge"))
            patches.enter_context(patch("src.ComposerSettings"))
            patches.enter_context(patch("src.LyricsService"))
            patches.enter_context(patch("src.MusixMatch"))
            playlist_class = patches.enter_context(patch("src.Playlist"))
            patches.enter_context(patch("src.Album"))
            ytdlp_class = patches.enter_context(patch("src.YTDLP"))
            patches.enter_context(patch("src.StreamService"))
            patches.enter_context(patch("src.FFmpeg"))
            patches.enter_context(patch("src.DownloadService"))
            patches.enter_context(patch("src.ExportService"))
            patches.enter_context(patch("src.OverlayServer"))
            patches.enter_context(patch("src.RemoteControl"))
            patches.enter_context(patch("src.register_blueprints"))
            patches.enter_context(patch("src.setup_debug"))
            setup_log_tee = patches.enter_context(
                patch("src.setup_log_tee", side_effect=lambda: startup_steps.append("log_tee"))
            )
            setup_logger = patches.enter_context(
                patch("src.setup_logger", side_effect=lambda: startup_steps.append("logger"))
            )
            session = session_class.return_value
            session.state = MagicMock()
            session.autoload_first_profile.side_effect = lambda: startup_steps.append("autoload")
            app = create_app()

        assert startup_steps[:3] == ["log_tee", "logger", "autoload"]
        setup_log_tee.assert_called_once_with()
        setup_logger.assert_called_once_with()
        session.autoload_first_profile.assert_called_once_with()
        session.start_cookie_refresh_loop.assert_called_once_with()
        assert session.method_calls[:2] == [
            call.autoload_first_profile(),
            call.start_cookie_refresh_loop(),
        ]
        session_class.assert_called_once_with(
            profiles=profile_class.return_value,
            playlist_cache=playlist_class.return_value,
        )
        assert app.extensions["youtube_music_session"] is session
        assert app.extensions["playlist_cache"] is playlist_class.return_value
        assert app.extensions["feedback_webhook_url"] == "https://hooks.example.test"
        load_feedback_webhook.assert_called_once_with()
        assert ytdlp_class.return_value.method_calls == [
            call.ensure_node_in_path(),
            call.activate_ytdlp_update(),
        ]
