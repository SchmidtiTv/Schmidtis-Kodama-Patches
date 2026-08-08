import threading
import time
import unittest

from src.lib.music.download import DownloadService
from src.lib.music.export import ExportService
from src.lib.runtime.maintenance import DelayedCleanup


class BlockingJob:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def run(self, *args: object) -> None:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        self.release.wait(timeout=2)
        with self.lock:
            self.active -= 1


class BackgroundWorkLimitTests(unittest.TestCase):
    def test_download_service_limits_running_and_queued_jobs(self) -> None:
        service = DownloadService(ytdlp=object())
        job = BlockingJob()
        service._download_bg = job.run  # type: ignore[method-assign]
        try:
            for index in range(service.MAX_QUEUED_DOWNLOADS):
                self.assertTrue(service.start(f"song-{index}", {}))
            self.assertFalse(service.start("over-capacity", {}))
            self._wait_until(lambda: job.active == service.MAX_CONCURRENT_DOWNLOADS)
            self.assertEqual(job.max_active, service.MAX_CONCURRENT_DOWNLOADS)
        finally:
            job.release.set()
            service._executor.shutdown(wait=True)

    def test_export_service_limits_running_and_queued_jobs(self) -> None:
        service = ExportService(ytdlp=object(), ffmpeg=object())
        job = BlockingJob()
        service._export_bg = job.run  # type: ignore[method-assign]
        try:
            for index in range(service.MAX_QUEUED_EXPORTS):
                self.assertTrue(service.start(f"song-{index}", "/tmp/out", "opus", {}))
            self.assertFalse(service.start("over-capacity", "/tmp/out", "opus", {}))
            self._wait_until(lambda: job.active == service.MAX_CONCURRENT_EXPORTS)
            self.assertEqual(job.max_active, service.MAX_CONCURRENT_EXPORTS)
        finally:
            job.release.set()
            service._executor.shutdown(wait=True)

    def test_delayed_cleanup_reschedules_without_extra_worker_threads(self) -> None:
        values = {"entry": "value"}
        DelayedCleanup.schedule_removal(values, "entry", delay=0.01)
        DelayedCleanup.schedule_removal(values, "entry", delay=0.08)
        time.sleep(0.03)
        self.assertIn("entry", values)
        self._wait_until(lambda: "entry" not in values)

    def _wait_until(self, predicate: object) -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if callable(predicate) and predicate():
                return
            time.sleep(0.01)
        self.fail("condition was not met")
