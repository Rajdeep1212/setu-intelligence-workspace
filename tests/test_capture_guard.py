import threading
import unittest
from pathlib import Path

from scripts.capture_guard import MemoryLow, guard_loader, watch


class CaptureGuardTests(unittest.TestCase):
    def test_refuses_a_load_below_the_minimum_and_allows_one_above(self):
        loads = []
        low = guard_loader(loads.append, 3.5, lambda: 3.4, lambda: False)
        with self.assertRaisesRegex(MemoryLow, "3.40 GB free before loading bge-m3"):
            low(Path("models/bge-m3"))
        self.assertEqual(loads, [])
        guard_loader(loads.append, 3.5, lambda: 3.6, lambda: False)(Path("models/bge-m3"))
        self.assertEqual(loads, [Path("models/bge-m3")])

    def test_reranker_waits_until_the_embedding_model_is_released(self):
        guarded = guard_loader(lambda _: None, 3.5, lambda: 6.0, lambda: True)
        with self.assertRaisesRegex(MemoryLow, "one at a time"):
            guarded(Path("models/bge-reranker-v2-m3"))

    def test_watch_aborts_once_when_memory_falls_under_the_floor(self):
        readings = iter([2.0, 1.4, 0.8, 0.5])
        reasons = []
        watch(1.0, lambda: next(readings), reasons.append, threading.Event(), interval=0)
        self.assertEqual(reasons, ["free memory fell to 0.80 GB (floor 1.0 GB)"])

    def test_watch_stops_quietly_when_the_capture_ends(self):
        stop = threading.Event()
        stop.set()
        reasons = []
        watch(1.0, lambda: 0.1, reasons.append, stop, interval=0)
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
