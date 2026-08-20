import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config import config_dirs
from src.lib.integrations.ffmpeg import FFmpeg


class FFmpegTests(unittest.TestCase):
    def test_managed_binary_is_preferred_on_non_windows_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            managed_dir = Path(directory)
            (managed_dir / "ffmpeg").touch()

            with (
                patch.object(config_dirs, "BIN_DIR", managed_dir),
                patch("src.lib.integrations.ffmpeg.sys.platform", "darwin"),
            ):
                self.assertEqual(FFmpeg().find(), str(managed_dir))

    def test_a_found_result_is_cached_across_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            managed_dir = Path(directory)
            (managed_dir / "ffmpeg").touch()

            with (
                patch.object(config_dirs, "BIN_DIR", managed_dir),
                patch("src.lib.integrations.ffmpeg.sys.platform", "darwin"),
            ):
                ffmpeg = FFmpeg()
                first = ffmpeg.find()
                (managed_dir / "ffmpeg").unlink()  # a rescan would now miss
                second = ffmpeg.find()

        self.assertEqual(first, str(managed_dir))
        self.assertEqual(second, first)

    def test_a_miss_is_not_cached_so_a_later_install_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            managed_dir = Path(directory)  # empty: ffmpeg not present yet

            with (
                patch.object(config_dirs, "BIN_DIR", managed_dir),
                # Avoid the darwin-only Homebrew fallback paths, which may genuinely exist on
                # the machine running this test.
                patch("src.lib.integrations.ffmpeg.sys.platform", "linux"),
                patch("shutil.which", return_value=None),
            ):
                ffmpeg = FFmpeg()
                self.assertFalse(ffmpeg.find())
                (managed_dir / "ffmpeg").touch()  # simulate download_stream() installing it
                self.assertEqual(ffmpeg.find(), str(managed_dir))

    def test_macos_latest_version_uses_static_build_release(self) -> None:
        response = MagicMock()
        response.json.return_value = {"tag_name": "b6.1.1"}

        with (
            patch("src.lib.integrations.ffmpeg.sys.platform", "darwin"),
            patch("src.lib.integrations.ffmpeg.requests.get", return_value=response) as get,
        ):
            self.assertEqual(FFmpeg().latest_version(), "6.1.1")

        get.assert_called_once_with(
            "https://api.github.com/repos/eugeneware/ffmpeg-static/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )

    def test_macos_download_installs_executable_atomically(self) -> None:
        response = MagicMock()
        response.headers = {"content-length": "1000000"}
        response.iter_content.return_value = [b"x" * 1_000_000]
        response.__enter__.return_value = response

        with tempfile.TemporaryDirectory() as directory:
            managed_dir = Path(directory)
            with (
                patch.object(config_dirs, "BIN_DIR", managed_dir),
                patch("src.lib.integrations.ffmpeg.sys.platform", "darwin"),
                patch("src.lib.integrations.ffmpeg.platform.machine", return_value="arm64"),
                patch("src.lib.integrations.ffmpeg.requests.get", return_value=response) as get,
            ):
                events = list(FFmpeg().download_stream())

            installed = managed_dir / "ffmpeg"
            self.assertTrue(installed.exists())
            self.assertEqual(installed.stat().st_mode & stat.S_IXUSR, stat.S_IXUSR)
            self.assertEqual(events[-1], 'data: {"status": "done"}\n\n')
            get.assert_called_once_with(
                "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-darwin-arm64",
                stream=True,
                timeout=30,
                allow_redirects=True,
            )


if __name__ == "__main__":
    unittest.main()
