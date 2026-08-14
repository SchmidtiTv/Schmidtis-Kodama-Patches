from unittest.mock import patch

from flask import Flask
from src.routes import blueprints, register_blueprints

from route_test_support import RouteTestCase


class RouteRegistrationTests(RouteTestCase):
    def test_all_migrated_routes_are_registered(self) -> None:
        rules = {str(rule) for rule in self.app.url_map.iter_rules() if rule.endpoint != "static"}
        expected = {
            "/auth/begin-add",
            "/auth/cookie-login",
            "/auth/end-add",
            "/auth/local-create",
            "/auth/logout",
            "/auth/refresh-cookies",
            "/auth/setup",
            "/auth/validate",
            "/profiles",
            "/profiles/",
            "/profiles/avatar",
            "/profiles/delete",
            "/profiles/rename",
            "/profiles/switch",
            "/lastfm/connect",
            "/lastfm/disconnect",
            "/lastfm/love",
            "/lastfm/now-playing",
            "/lastfm/scrobble",
            "/lastfm/session",
            "/lastfm/status",
            "/lastfm/unlove",
            "/lyrics",
            "/lyrics/custom",
            "/lyrics/custom/<video_id>",
            "/lyrics/unison/versions",
            "/romanize-lyrics",
            "/translate-lyrics",
            "/unison/auth/nickname",
            "/unison/auth/nickname/check",
            "/unison/displayname/<key_id>",
            "/unison/lyrics/<lyrics_id>/report",
            "/unison/lyrics/<lyrics_id>/vote",
            "/composer-app/",
            "/composer-app/<path:subpath>",
            "/composer-bridge/audio/<video_id>",
            "/composer-bridge/autocache",
            "/composer-bridge/health",
            "/composer-bridge/thumb/<video_id>",
            "/song/download/<video_id>",
            "/song/download/status/<video_id>",
            "/downloads/queue",
            "/song/cached/<video_id>",
            "/song/cached/list",
            "/songs/cached/delete-batch",
            "/song/export/<video_id>",
            "/song/export/status/<video_id>",
            "/song/export/ffmpeg-available",
            "/ffmpeg/status",
            "/ffmpeg/check-update",
            "/ffmpeg/download",
            "/ytdlp/check-update",
            "/ytdlp/update",
            "/cache/clear",
            "/cache/settings",
            "/cache/stats",
            "/library/playlists",
            "/library/albums",
            "/library/artists",
            "/playlist/create",
            "/playlist/<playlist_id>/add",
            "/playlist/<playlist_id>/remove",
            "/playlist/<playlist_id>/edit",
            "/playlist/<playlist_id>",
            "/playlist/<playlist_id>/stream",
            "/radio/<playlist_id>",
            "/album/<browse_id>",
            "/artist/<browse_id>",
            "/artist/<browse_id>/members",
            "/artist/<browse_id>/subscribe",
            "/artist/<browse_id>/unsubscribe",
            "/song/meta/<video_id>",
            "/song/info/<video_id>",
            "/song/stats/<video_id>",
            "/song/credits/<video_id>",
            "/podcast/<playlist_id>",
            "/mood/categories",
            "/mood/playlists",
            "/debug/info",
            "/api/local-fonts",
            "/network/ipv4-first",
            "/overlay",
            "/overlay/stream",
            "/overlay/push",
            "/overlay/config",
            "/overlay/server/start",
            "/overlay/server/stop",
            "/overlay/status",
            "/remote/_enable",
            "/remote/_status",
            "/remote/_device",
            "/remote/_push",
            "/remote/_poll",
            "/remote/_sync",
            "/remote/hello",
            "/remote/state",
            "/remote/cmd",
            "/remote",
            "/artist_albums",
            "/home",
            "/imgproxy",
            "/like/<video_id>",
            "/liked",
            "/liked/ids",
            "/search",
            "/search/suggestions",
            "/shutdown",
            "/status",
            "/stream/<video_id>",
            "/stream-prepare/<video_id>",
            "/audio-stream/<video_id>",
            "/audio-stream/<video_id>/warm",
            "/video-sync/offset/<video_id>",
            "/video-sync/stream/<video_id>",
            "/playlist/<playlist_id>/mix",
            "/playlist/<playlist_id>/mix/analysis",
            "/playlist/<playlist_id>/mix/analysis/<job_id>",
            "/ytmusic/history",
            "/news",
            "/feedback",
            "/clientlog",
        }
        assert rules == expected

    def test_route_methods_and_registrations_are_not_duplicated(self) -> None:
        rules = [rule for rule in self.app.url_map.iter_rules() if rule.endpoint != "static"]
        signatures = [(str(rule), frozenset(rule.methods or set())) for rule in rules]
        assert len(signatures) == len(set(signatures))

        methods_by_rule: dict[str, set[str]] = {}
        for rule in rules:
            methods_by_rule.setdefault(str(rule), set()).update(
                (rule.methods or set()) - {"HEAD", "OPTIONS"}
            )

        expected_methods = {
            "/cache/settings": {"GET", "POST"},
            "/composer-bridge/autocache": {"GET", "POST"},
            "/lyrics/custom/<video_id>": {"GET", "DELETE"},
            "/network/ipv4-first": {"GET", "POST"},
            "/overlay/config": {"GET", "POST"},
            "/playlist/<playlist_id>": {"GET", "DELETE"},
            "/playlist/<playlist_id>/mix": {"GET", "PUT", "DELETE"},
            "/shutdown": {"GET", "POST"},
            "/song/cached/<video_id>": {"GET", "DELETE"},
            "/unison/auth/nickname": {"PUT", "DELETE"},
            "/unison/lyrics/<lyrics_id>/vote": {"POST", "DELETE"},
        }
        assert {rule: methods_by_rule[rule] for rule in expected_methods} == expected_methods

    def test_blueprint_registry_is_unique_and_clientlog_remains_debug_only(self) -> None:
        names = [blueprint.name for blueprint, _ in blueprints]
        assert len(names) == len(set(names))
        assert [(blueprint.name, is_debug) for blueprint, is_debug in blueprints].count(
            ("clientlog", True)
        ) == 1

        production_app = Flask(__name__)
        with patch("src.routes.Config.DEBUG", False):
            register_blueprints(production_app)

        production_rules = {str(rule) for rule in production_app.url_map.iter_rules()}
        assert "/clientlog" not in production_rules
        assert "/status" in production_rules
