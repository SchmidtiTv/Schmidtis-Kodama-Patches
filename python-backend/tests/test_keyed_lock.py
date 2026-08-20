import threading
import unittest

from src.lib.runtime.keyed_lock import KeyedLock


class KeyedLockTests(unittest.TestCase):
    def test_serializes_the_same_key(self) -> None:
        lock = KeyedLock()
        first_started = threading.Event()
        release_first = threading.Event()
        second_started = threading.Event()

        def hold_first() -> None:
            with lock.acquire("a"):
                first_started.set()
                self.assertTrue(release_first.wait(timeout=2))

        def hold_second() -> None:
            with lock.acquire("a"):
                second_started.set()

        first = threading.Thread(target=hold_first)
        second = threading.Thread(target=hold_second)
        first.start()
        self.assertTrue(first_started.wait(timeout=2))
        second.start()
        self.assertFalse(second_started.wait(timeout=0.1))
        release_first.set()
        first.join(timeout=2)
        second.join(timeout=2)
        self.assertTrue(second_started.is_set())

    def test_does_not_serialize_different_keys(self) -> None:
        lock = KeyedLock()
        first_started = threading.Event()
        release_first = threading.Event()
        second_started = threading.Event()

        def hold_first() -> None:
            with lock.acquire("a"):
                first_started.set()
                self.assertTrue(release_first.wait(timeout=2))

        def hold_second() -> None:
            with lock.acquire("b"):
                second_started.set()

        first = threading.Thread(target=hold_first)
        second = threading.Thread(target=hold_second)
        first.start()
        self.assertTrue(first_started.wait(timeout=2))
        second.start()
        self.assertTrue(second_started.wait(timeout=2))
        release_first.set()
        first.join(timeout=2)
        second.join(timeout=2)

    def test_table_is_empty_after_all_holders_release(self) -> None:
        lock = KeyedLock()
        with lock.acquire("a"):
            pass
        with lock.acquire("b"):
            pass
        self.assertEqual(lock._entries, {})

    def test_reentrant_use_from_different_calls_is_sequential_and_correct(self) -> None:
        lock = KeyedLock()
        order = []

        def worker(label: str) -> None:
            with lock.acquire("shared"):
                order.append(f"{label}-start")
                order.append(f"{label}-end")

        threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

        # Every start must be immediately followed by its own end — no interleaving.
        for i in range(0, len(order), 2):
            label = order[i].rsplit("-", 1)[0]
            self.assertEqual(order[i + 1], f"{label}-end")


if __name__ == "__main__":
    unittest.main()
