import tempfile
import threading
import time
import unittest
from pathlib import Path

from src.lib.music.mix_analysis import MixAnalysisService
from src.lib.music.playlist_mix import PlaylistMix
from src.lib.runtime.metadata_cache import MetadataCache


class BlockingAnalyzer:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def analyze(self, path: str, video_id: str) -> dict[str, object]:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        self.started.set()
        self.release.wait(timeout=2)
        with self.lock:
            self.active -= 1
        return {"videoId": video_id, "status": "complete"}


class StreamServiceStub:
    def prepare_download(self, video_id: str) -> tuple[dict[str, str], int]:
        return {"path": f"/{video_id}.m4a"}, 200


class MixAnalysisServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        cache = MetadataCache(Path(self.tempdir.name) / "cache.sqlite3")
        self.analyzer = BlockingAnalyzer()
        self.service = MixAnalysisService(
            stream_service=StreamServiceStub(),
            metadata_cache=cache,
            playlist_mix=PlaylistMix(cache),
            analyzer=self.analyzer,
        )

    def tearDown(self) -> None:
        self.analyzer.release.set()
        self.tempdir.cleanup()

    def test_reuses_matching_job_and_supersedes_changed_job_without_parallel_analysis(self) -> None:
        first_tracks = [{"instanceId": "one", "videoId": "video-one"}]
        first = self.service.start(None, "playlist", first_tracks)
        self.assertTrue(self.analyzer.started.wait(timeout=1))

        duplicate = self.service.start(None, "playlist", first_tracks)
        self.assertEqual(duplicate["jobId"], first["jobId"])

        second = self.service.start(None, "playlist", [{"instanceId": "two", "videoId": "video-two"}])
        self.assertNotEqual(second["jobId"], first["jobId"])
        self.assertEqual(self.service.get_job(None, "playlist", first["jobId"])["status"], "cancelled")

        self.analyzer.release.set()
        self._wait_for_status(second["jobId"], "complete")
        self.assertEqual(self.analyzer.max_active, 1)

    def _wait_for_status(self, job_id: str, expected_status: str) -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            job = self.service.get_job(None, "playlist", job_id)
            if job and job["status"] == expected_status:
                return
            time.sleep(0.01)
        self.fail(f"job {job_id} did not reach {expected_status}")
