import time

from flask import Flask
from flask_cors import CORS

from src.config import Config, config_dirs
from src.lib import (
    YTDLP,
    Album,
    AlbumDetailsService,
    ArtistSubscriptionService,
    BandMemberFinder,
    CacheSettings,
    ComposerBridge,
    ComposerSettings,
    DiscordFeedbackWebhookClient,
    DownloadService,
    ExportService,
    FeedbackService,
    FFmpeg,
    HttpUnisonClient,
    ImageProxyService,
    LastFM,
    LibraryService,
    LikedSongsService,
    ListeningHistoryService,
    LocalMusicRepository,
    LyricsService,
    MetadataCache,
    MixAnalysisService,
    MusixMatch,
    NetworkSettings,
    NumpyTrackAnalyzer,
    OverlayServer,
    Playlist,
    PlaylistMix,
    PlaylistService,
    Profile,
    ProviderCollection,
    RemoteControl,
    RequestsHttpTransport,
    RestrictedImageProxyClient,
    ReturnYoutubeDislikeProvider,
    SearchService,
    SessionActiveMusicProfile,
    SongCreditsCache,
    SongCreditsService,
    SongRatingService,
    SongStatisticsCapabilities,
    SongStatisticsService,
    StreamService,
    VideoSyncService,
    YoutubeCapabilities,
    YoutubeMusicCatalogProvider,
    YoutubeMusicLibraryProvider,
    YoutubeMusicPlaylistProvider,
    YoutubeMusicSession,
    YoutubePlaylistAudioEnricher,
    YoutubeSongCreditsProvider,
    feedback_log_snapshot,
    load_feedback_webhook,
    setup_debug,
    setup_log_tee,
    setup_logger,
)
from src.routes import register_blueprints

CORS_ORIGINS = [
    "http://localhost:1421",  # Tauri dev server
    "tauri://localhost",  # Tauri production (Windows/Linux)
    "https://tauri.localhost",  # Tauri production (Tauri 2.x, WebView2)
    "http://tauri.localhost",  # fallback
    "http://localhost",
    "http://127.0.0.1",
]


def create_app() -> Flask:
    try:
        setup_log_tee()
        setup_logger()
        app = Flask(__name__)
        app.config.from_object(Config)
        http = RequestsHttpTransport()
        # Cache CORS preflights so the frequent local overlay updates do not issue
        # an OPTIONS request before every browser POST.
        CORS(app, origins=CORS_ORIGINS, max_age=600)
        app.extensions["server_start_time"] = time.time()
        feedback_webhook_url = load_feedback_webhook()
        feedback_client = (
            DiscordFeedbackWebhookClient(http=http, webhook_url=feedback_webhook_url)
            if feedback_webhook_url
            else None
        )
        app.extensions["feedback_service"] = FeedbackService(
            client=feedback_client,
            log_source=feedback_log_snapshot,
        )
        app.extensions["network_settings"] = NetworkSettings()
        song_credits_cache = SongCreditsCache()

        profile_repository = Profile()
        app.extensions["profile_repository"] = profile_repository
        metadata_cache = MetadataCache(config_dirs.CACHE_DATABASE)
        app.extensions["metadata_cache"] = metadata_cache
        mix_database = MetadataCache(config_dirs.MIX_DATABASE)
        metadata_cache.move_categories_to(
            mix_database,
            ("playlist_mix", "mix_audio_analysis"),
        )
        app.extensions["mix_database"] = mix_database
        playlist_cache = Playlist(metadata_cache=metadata_cache)
        app.extensions["playlist_cache"] = playlist_cache
        app.extensions["playlist_mix"] = PlaylistMix(mix_database)
        music_session = YoutubeMusicSession(
            profiles=profile_repository,
            playlist_cache=playlist_cache,
        )
        music_session.autoload_first_profile()
        music_session.start_cookie_refresh_loop()
        app.extensions["youtube_music_session"] = music_session
        app.extensions["lastfm_client"] = LastFM()
        cache_settings = CacheSettings(metadata_cache=metadata_cache)
        app.extensions["cache_settings"] = cache_settings
        app.extensions["image_proxy_service"] = ImageProxyService(
            client=RestrictedImageProxyClient(http=http),
            cache_settings=cache_settings,
            cache_directory=config_dirs.IMG_CACHE_DIR,
            cache_ttl=Config.IMG_CACHE_TTL,
        )
        app.extensions["unison_client"] = HttpUnisonClient(http=http)
        app.extensions["composer_bridge"] = ComposerBridge(
            settings=ComposerSettings(),
            cache_settings=cache_settings,
            music_session=app.extensions["youtube_music_session"],
        )
        app.extensions["lyrics_service"] = LyricsService(
            cache_settings=cache_settings,
            musixmatch=MusixMatch(),
            metadata_cache=metadata_cache,
        )
        album_cache = Album(metadata_cache=metadata_cache)
        app.extensions["album_cache"] = album_cache
        app.extensions["band_member_finder"] = BandMemberFinder()

        providers = ProviderCollection()
        youtube_catalog = YoutubeMusicCatalogProvider(
            session=music_session,
            metadata_cache=metadata_cache,
        )
        youtube_library = YoutubeMusicLibraryProvider(session=music_session)
        youtube_playlists = YoutubeMusicPlaylistProvider(session=music_session)
        youtube_credits = YoutubeSongCreditsProvider(http=http)
        providers.use(
            YoutubeCapabilities(
                catalog=youtube_catalog,
                library=youtube_library,
                playlists=youtube_playlists,
                credits=youtube_credits,
            )
        )
        active_profile = SessionActiveMusicProfile(music_session, profile_repository)
        local_music = LocalMusicRepository(profile_repository)
        audio_enricher = YoutubePlaylistAudioEnricher(music_session, metadata_cache)
        app.extensions["library_service"] = LibraryService(
            profile_context=active_profile,
            remote_library=youtube_library,
            local_library=local_music,
        )
        app.extensions["liked_songs_service"] = LikedSongsService(
            profile_context=active_profile,
            remote_library=youtube_library,
            local_library=local_music,
            audio_enricher=audio_enricher,
        )
        app.extensions["song_rating_service"] = SongRatingService(
            profile_context=active_profile,
            remote_library=youtube_library,
            local_library=local_music,
        )
        app.extensions["artist_subscription_service"] = ArtistSubscriptionService(
            profile_context=active_profile,
            remote_library=youtube_library,
        )
        app.extensions["listening_history_service"] = ListeningHistoryService(
            profile_context=active_profile,
            remote_library=youtube_library,
        )
        app.extensions["playlist_service"] = PlaylistService(
            profile_context=active_profile,
            remote_playlists=youtube_playlists,
            remote_radio=youtube_playlists,
            local_playlists=local_music,
            cache=playlist_cache,
            cache_settings=cache_settings,
            audio_enricher=audio_enricher,
        )
        app.extensions["song_credits_service"] = SongCreditsService(
            provider=youtube_credits,
            cache=song_credits_cache,
        )
        app.extensions["search_service"] = SearchService(youtube_catalog)
        app.extensions["album_details_service"] = AlbumDetailsService(
            catalog=youtube_catalog,
            album_cache=album_cache,
            cache_settings=cache_settings,
        )
        statistics_provider = ReturnYoutubeDislikeProvider(http=http)
        providers.use(SongStatisticsCapabilities(provider=statistics_provider))
        app.extensions["song_statistics_service"] = SongStatisticsService(providers.song_statistics)

        ytdlp = YTDLP(
            profiles=profile_repository,
            music_state=app.extensions["youtube_music_session"].state,
        )
        app.extensions["ytdlp"] = ytdlp
        app.extensions["stream_service"] = StreamService(ytdlp=ytdlp)

        ffmpeg = FFmpeg()
        app.extensions["ffmpeg"] = ffmpeg
        app.extensions["mix_analysis_service"] = MixAnalysisService(
            stream_service=app.extensions["stream_service"],
            metadata_cache=mix_database,
            playlist_mix=app.extensions["playlist_mix"],
            analyzer=NumpyTrackAnalyzer(ffmpeg),
        )
        app.extensions["video_sync_service"] = VideoSyncService(
            music_session=music_session,
            ytdlp=ytdlp,
            ffmpeg=ffmpeg,
        )
        app.extensions["download_service"] = DownloadService(ytdlp=ytdlp)
        app.extensions["export_service"] = ExportService(ytdlp=ytdlp, ffmpeg=ffmpeg)

        app.extensions["overlay_server"] = OverlayServer()
        app.extensions["remote_control"] = RemoteControl()

        register_blueprints(app)

        setup_debug(app)
        # yt-dlp needs Node.js for nsig decryption before it handles any request.
        ytdlp.ensure_node_in_path()
        ytdlp.activate_ytdlp_update()

        return app

    except Exception as err:
        raise RuntimeError("Failed to create Flask application.") from err
