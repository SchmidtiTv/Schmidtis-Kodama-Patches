import logging
from io import StringIO
from unittest import TestCase

from src.lib.runtime.logging import (
    DEBUG_LOG,
    DEBUG_LOG_LOCK,
    LogTee,
    _DropNoisyAccessLogs,
    setup_logger,
)


class RuntimeLoggingTests(TestCase):
    def setUp(self) -> None:
        self._root_level = logging.getLogger().level
        self._werkzeug_level = logging.getLogger("werkzeug").level

    def tearDown(self) -> None:
        logging.getLogger().setLevel(self._root_level)
        logging.getLogger("werkzeug").setLevel(self._werkzeug_level)

    def test_setup_logger_raises_the_root_level_so_backend_records_reach_the_ring(self) -> None:
        logging.getLogger().setLevel(logging.WARNING)

        setup_logger()

        self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_noisy_access_log_filter_drops_timer_driven_endpoints(self) -> None:
        drop_filter = _DropNoisyAccessLogs()
        record = logging.LogRecord(
            "werkzeug", logging.INFO, __file__, 0,
            '127.0.0.1 - - "POST /overlay/push HTTP/1.1" 200 -', (), None,
        )

        self.assertFalse(drop_filter.filter(record))

    def test_noisy_access_log_filter_keeps_diagnostic_records(self) -> None:
        drop_filter = _DropNoisyAccessLogs()
        record = logging.LogRecord(
            "backend", logging.INFO, __file__, 0,
            "stream tier resolved in 120ms", (), None,
        )

        self.assertTrue(drop_filter.filter(record))

    def test_log_tee_includes_printed_lines_in_the_debug_ring(self) -> None:
        with DEBUG_LOG_LOCK:
            DEBUG_LOG.clear()

        stream = StringIO()
        tee = LogTee(stream, "INFO")
        tee.write("printed diagnostic\n")

        self.assertEqual(stream.getvalue(), "printed diagnostic\n")
        with DEBUG_LOG_LOCK:
            entry = DEBUG_LOG[-1]
        self.assertEqual(entry["level"], "INFO")
        self.assertEqual(entry["msg"], "printed diagnostic")
