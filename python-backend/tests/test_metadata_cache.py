import tempfile
from pathlib import Path

from src.lib.runtime.cache import CacheSettings
from src.lib.runtime.metadata_cache import MetadataCache


class MetadataCacheTests:
    def setup_method(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.cache = MetadataCache(Path(self.temporary_directory.name) / "cache.sqlite3")

    def teardown_method(self) -> None:
        self.temporary_directory.cleanup()

    def test_stores_and_reports_structured_entries_by_category(self) -> None:
        self.cache.put("albums", "album-1", {"title": "Album", "tracks": []})

        assert self.cache.get("albums", "album-1") == {"title": "Album", "tracks": []}
        size, count = self.cache.stats("albums")
        assert size > 0
        assert count == 1
        assert self.cache.stats("lyrics") == (0, 0)

        self.cache.clear("albums")
        assert self.cache.get("albums", "album-1") is None

    def test_expired_entries_are_removed_on_read(self) -> None:
        self.cache.put("playlists", "profile:list", {"tracks": []})

        assert self.cache.get("playlists", "profile:list", ttl=-1) is None
        assert self.cache.stats("playlists") == (0, 0)

    def test_cache_settings_survive_backend_restart(self) -> None:
        settings = CacheSettings(metadata_cache=self.cache)
        settings.update({"images": False, "maxCacheMb": 500})

        restored = CacheSettings(metadata_cache=MetadataCache(self.cache.path))

        assert not restored.enabled["images"]
        assert restored.max_cache_mb == 500

    def test_audio_counterparts_use_their_own_table(self) -> None:
        audio: dict[str, object] = {
            "videoId": "audio-id",
            "title": "Take On Me",
            "videoType": "MUSIC_VIDEO_TYPE_ATV",
        }

        self.cache.put_audio_counterpart("video-id", audio)

        assert self.cache.get_audio_counterpart("video-id") == audio
        assert self.cache.stats("audio_counterparts") == (0, 0)
        size, count = self.cache.audio_counterpart_stats()
        assert size > 0
        assert count == 1

        self.cache.clear_audio_counterparts()
        assert self.cache.get_audio_counterpart("video-id") is None

    def test_moves_selected_categories_to_a_separate_database(self) -> None:
        destination = MetadataCache(Path(self.temporary_directory.name) / "mix.sqlite3")
        self.cache.put("playlists", "playlist-1", {"title": "Cached playlist"})
        self.cache.put("playlist_mix", "profile:playlist-1", {"enabled": True})
        self.cache.put("mix_audio_analysis", "v1:video-1", {"bpm": 128, "camelotKey": "8A"})

        self.cache.move_categories_to(
            destination,
            ("playlist_mix", "mix_audio_analysis"),
        )

        assert self.cache.get("playlists", "playlist-1") == {"title": "Cached playlist"}
        assert self.cache.get("playlist_mix", "profile:playlist-1") is None
        assert self.cache.get("mix_audio_analysis", "v1:video-1") is None
        assert destination.get("playlist_mix", "profile:playlist-1") == {"enabled": True}
        assert destination.get("mix_audio_analysis", "v1:video-1") == {
            "bpm": 128,
            "camelotKey": "8A",
        }

    def test_category_migration_keeps_a_newer_destination_value(self) -> None:
        destination = MetadataCache(Path(self.temporary_directory.name) / "mix.sqlite3")
        self.cache.put("mix_audio_analysis", "v1:video-1", {"bpm": 120})
        destination.put("mix_audio_analysis", "v1:video-1", {"bpm": 128})

        self.cache.move_categories_to(destination, ("mix_audio_analysis",))

        assert destination.get("mix_audio_analysis", "v1:video-1") == {"bpm": 128}
        assert self.cache.get("mix_audio_analysis", "v1:video-1") is None
