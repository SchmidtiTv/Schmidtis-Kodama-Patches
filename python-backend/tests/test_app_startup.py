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
            feedback_client_class = patches.enter_context(patch("src.DiscordFeedbackWebhookClient"))
            feedback_service_class = patches.enter_context(patch("src.FeedbackService"))
            image_client_class = patches.enter_context(patch("src.RestrictedImageProxyClient"))
            image_service_class = patches.enter_context(patch("src.ImageProxyService"))
            unison_client_class = patches.enter_context(patch("src.HttpUnisonClient"))
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
            album_class = patches.enter_context(patch("src.Album"))
            album_details_service_class = patches.enter_context(patch("src.AlbumDetailsService"))
            search_service_class = patches.enter_context(patch("src.SearchService"))
            youtube_catalog_class = patches.enter_context(patch("src.YoutubeMusicCatalogProvider"))
            youtube_library_class = patches.enter_context(patch("src.YoutubeMusicLibraryProvider"))
            youtube_playlists_class = patches.enter_context(
                patch("src.YoutubeMusicPlaylistProvider")
            )
            youtube_credits_class = patches.enter_context(patch("src.YoutubeSongCreditsProvider"))
            credits_cache_class = patches.enter_context(patch("src.SongCreditsCache"))
            credits_service_class = patches.enter_context(patch("src.SongCreditsService"))
            audio_enricher_class = patches.enter_context(patch("src.YoutubePlaylistAudioEnricher"))
            active_profile_class = patches.enter_context(patch("src.SessionActiveMusicProfile"))
            local_music_class = patches.enter_context(patch("src.LocalMusicRepository"))
            library_service_class = patches.enter_context(patch("src.LibraryService"))
            liked_songs_service_class = patches.enter_context(patch("src.LikedSongsService"))
            rating_service_class = patches.enter_context(patch("src.SongRatingService"))
            subscription_service_class = patches.enter_context(
                patch("src.ArtistSubscriptionService")
            )
            history_service_class = patches.enter_context(patch("src.ListeningHistoryService"))
            playlist_service_class = patches.enter_context(patch("src.PlaylistService"))
            youtube_capabilities_class = patches.enter_context(patch("src.YoutubeCapabilities"))
            provider_collection_class = patches.enter_context(patch("src.ProviderCollection"))
            http_transport_class = patches.enter_context(patch("src.RequestsHttpTransport"))
            statistics_provider_class = patches.enter_context(
                patch("src.ReturnYoutubeDislikeProvider")
            )
            statistics_capabilities_class = patches.enter_context(
                patch("src.SongStatisticsCapabilities")
            )
            statistics_service_class = patches.enter_context(patch("src.SongStatisticsService"))
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
        assert app.extensions["song_statistics_service"] is statistics_service_class.return_value
        load_feedback_webhook.assert_called_once_with()
        feedback_client_class.assert_called_once_with(
            http=http_transport_class.return_value,
            webhook_url="https://hooks.example.test",
        )
        feedback_service_class.assert_called_once()
        image_client_class.assert_called_once_with(http=http_transport_class.return_value)
        image_service_class.assert_called_once()
        unison_client_class.assert_called_once_with(http=http_transport_class.return_value)
        statistics_provider_class.assert_called_once_with(http=http_transport_class.return_value)
        statistics_capabilities_class.assert_called_once_with(
            provider=statistics_provider_class.return_value
        )
        youtube_catalog_class.assert_called_once_with(
            session=session,
            metadata_cache=app.extensions["metadata_cache"],
        )
        youtube_library_class.assert_called_once_with(session=session)
        youtube_playlists_class.assert_called_once_with(session=session)
        youtube_credits_class.assert_called_once_with(http=http_transport_class.return_value)
        youtube_capabilities_class.assert_called_once_with(
            catalog=youtube_catalog_class.return_value,
            library=youtube_library_class.return_value,
            playlists=youtube_playlists_class.return_value,
            credits=youtube_credits_class.return_value,
        )
        assert provider_collection_class.return_value.use.call_args_list == [
            call(youtube_capabilities_class.return_value),
            call(statistics_capabilities_class.return_value),
        ]
        search_service_class.assert_called_once_with(youtube_catalog_class.return_value)
        active_profile_class.assert_called_once_with(session, profile_class.return_value)
        local_music_class.assert_called_once_with(profile_class.return_value)
        audio_enricher_class.assert_called_once_with(session, app.extensions["metadata_cache"])
        library_service_class.assert_called_once_with(
            profile_context=active_profile_class.return_value,
            remote_library=youtube_library_class.return_value,
            local_library=local_music_class.return_value,
        )
        liked_songs_service_class.assert_called_once_with(
            profile_context=active_profile_class.return_value,
            remote_library=youtube_library_class.return_value,
            local_library=local_music_class.return_value,
            audio_enricher=audio_enricher_class.return_value,
        )
        rating_service_class.assert_called_once_with(
            profile_context=active_profile_class.return_value,
            remote_library=youtube_library_class.return_value,
            local_library=local_music_class.return_value,
        )
        subscription_service_class.assert_called_once_with(
            profile_context=active_profile_class.return_value,
            remote_library=youtube_library_class.return_value,
        )
        history_service_class.assert_called_once_with(
            profile_context=active_profile_class.return_value,
            remote_library=youtube_library_class.return_value,
        )
        playlist_service_class.assert_called_once_with(
            profile_context=active_profile_class.return_value,
            remote_playlists=youtube_playlists_class.return_value,
            remote_radio=youtube_playlists_class.return_value,
            local_playlists=local_music_class.return_value,
            cache=playlist_class.return_value,
            cache_settings=app.extensions["cache_settings"],
            audio_enricher=audio_enricher_class.return_value,
        )
        credits_service_class.assert_called_once_with(
            provider=youtube_credits_class.return_value,
            cache=credits_cache_class.return_value,
        )
        album_details_service_class.assert_called_once_with(
            catalog=youtube_catalog_class.return_value,
            album_cache=album_class.return_value,
            cache_settings=app.extensions["cache_settings"],
        )
        statistics_service_class.assert_called_once_with(
            provider_collection_class.return_value.song_statistics
        )
        http_transport_class.return_value.request.assert_not_called()
        assert ytdlp_class.return_value.method_calls == [
            call.ensure_node_in_path(),
            call.activate_ytdlp_update(),
        ]
