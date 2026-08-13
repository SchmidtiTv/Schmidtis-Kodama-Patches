"""Tests for development and packaged filesystem layouts."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.config import ConfigDirs, ConfigYTDLP


class ConfigDirsTests:
    """Verify that development caches are isolated without moving user data."""

    def test_development_cache_is_migrated_out_of_the_backend_root(self) -> None:
        """Copy legacy cache contents before switching to the new paths."""
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            legacy_cache = project_root / "album_cache"
            legacy_cache.mkdir()
            (legacy_cache / "album.json").write_text("cached", encoding="utf-8")
            (project_root / "cache.sqlite3").write_bytes(b"database")
            profiles = project_root / "profiles"
            profiles.mkdir()
            (profiles / "profile.json").write_text("profile", encoding="utf-8")

            with (
                patch("src.config.PROJECT_ROOT", project_root),
                patch.object(sys, "frozen", new=False, create=True),
            ):
                config_dirs = ConfigDirs()

            assert config_dirs.CACHE_DIR == project_root / ".cache"
            assert (config_dirs.ALBUM_CACHE_DIR / "album.json").read_text(
                encoding="utf-8"
            ) == "cached"
            assert config_dirs.CACHE_DATABASE.read_bytes() == b"database"
            assert not legacy_cache.exists()
            assert not (project_root / "cache.sqlite3").exists()
            assert (profiles / "profile.json").exists()

    def test_explicit_base_directory_keeps_the_existing_layout(self) -> None:
        """Keep tests and packaged-style callers compatible with a flat base path."""
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)

            config_dirs = ConfigDirs(base_dir)

            assert config_dirs.CACHE_DIR == base_dir
            assert config_dirs.CACHE_DATABASE == base_dir / "cache.sqlite3"

    def test_migration_does_not_overwrite_an_existing_destination(self) -> None:
        """Retain both copies when an earlier cache already occupies the new path."""
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            legacy_database = project_root / "cache.sqlite3"
            legacy_database.write_bytes(b"legacy")
            destination_database = project_root / ".cache" / "cache.sqlite3"
            destination_database.parent.mkdir()
            destination_database.write_bytes(b"current")

            with (
                patch("src.config.PROJECT_ROOT", project_root),
                patch.object(sys, "frozen", new=False, create=True),
            ):
                ConfigDirs()

            assert legacy_database.read_bytes() == b"legacy"
            assert destination_database.read_bytes() == b"current"

    def test_ytdlp_config_separates_legacy_and_encrypted_cookie_paths(self) -> None:
        """Keep migration input separate from the encrypted destination."""
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            cache_dir = base_dir / ".cache"

            config = ConfigYTDLP(base_dir, cache_dir)

            assert config.LEGACY_BROWSER_COOKIE_FILE == base_dir / "browser_cookies.txt"
            assert config.BROWSER_COOKIE_STORE_FILE == cache_dir / "browser-cookies.enc"
