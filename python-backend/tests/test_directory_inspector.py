import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.lib.runtime.maintenance import DirectoryInspector


class DirectoryInspectorTests(unittest.TestCase):
    def test_caches_recent_results_and_rescans_after_the_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "a.txt").write_bytes(b"12345")

            clock = [100.0]
            with patch(
                "src.lib.runtime.maintenance.time.monotonic", side_effect=lambda: clock[0]
            ):
                first = DirectoryInspector.size_and_file_count(path)
                (path / "b.txt").write_bytes(b"67")
                # Still within the TTL window: the stale (cached) result is reused rather than
                # rescanning the directory.
                second = DirectoryInspector.size_and_file_count(path)
                self.assertEqual(second, first)

                clock[0] += DirectoryInspector._CACHE_TTL_SECONDS + 1
                third = DirectoryInspector.size_and_file_count(path)

        self.assertEqual(first, (5, 1))
        self.assertEqual(third, (7, 2))


if __name__ == "__main__":
    unittest.main()
