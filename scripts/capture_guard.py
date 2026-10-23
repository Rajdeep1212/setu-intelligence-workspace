"""Memory guard for the M2.2 baseline capture (owner rule, 14 Oct 2026).

Runs `python -m eval.everyday_evaluation --capture` with two checks:
- before each model is compiled, at least SETU_MIN_FREE_GB must be free,
  and the reranker may not load while the embedding model is still held;
- while it runs, the process stops at once if free memory falls under
  SETU_ABORT_FREE_GB. The retrieval file is written only at the very end,
  so an abort leaves the saved file untouched.

Started by scripts/capture_everyday_baseline.ps1; not used by the app.
"""

from __future__ import annotations

import ctypes
import os
import runpy
import sys
import threading
from pathlib import Path
from typing import Callable

ABORT_EXIT = 4


class MemoryLow(RuntimeError):
    pass


def free_gb() -> float:
    """Free physical memory in GB (Windows; the capture runs on the owner's laptop)."""

    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                    ("available", ctypes.c_ulonglong), ("page_total", ctypes.c_ulonglong), ("page_free", ctypes.c_ulonglong),
                    ("virtual_total", ctypes.c_ulonglong), ("virtual_free", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong)]

    status = Status(length=ctypes.sizeof(Status))
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    return status.available / 1024**3


def guard_loader(load: Callable, minimum_gb: float, free: Callable[[], float], embedder_loaded: Callable[[], bool]) -> Callable:
    """Wrap the model compiler so each load is checked first."""

    def guarded(model_dir: Path):
        if Path(model_dir).name == "bge-reranker-v2-m3" and embedder_loaded():
            raise MemoryLow("the embedding model is still loaded; models must load one at a time")
        available = free()
        if available < minimum_gb:
            raise MemoryLow(f"{available:.2f} GB free before loading {Path(model_dir).name}; at least {minimum_gb} GB is needed")
        print(f"[guard] loading {Path(model_dir).name} with {available:.2f} GB free", flush=True)
        return load(model_dir)

    return guarded


def watch(floor_gb: float, free: Callable[[], float], abort: Callable[[str], None], stop: threading.Event, interval: float = 1.0) -> None:
    """Call abort once if free memory falls under the floor."""
    while not stop.wait(interval):
        available = free()
        if available < floor_gb:
            abort(f"free memory fell to {available:.2f} GB (floor {floor_gb} GB)")
            return


def _abort(reason: str) -> None:
    print(f"[guard] ABORTED: {reason}. Nothing was written.", flush=True)
    os._exit(ABORT_EXIT)  # stop model work at once; the PowerShell runner stops the database


def main() -> int:
    minimum = float(os.environ.get("SETU_MIN_FREE_GB", "3.5"))
    floor = float(os.environ.get("SETU_ABORT_FREE_GB", "1.0"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.retrieval import embeddings, openvino_backend

    openvino_backend._load_compiled_model = guard_loader(
        openvino_backend._load_compiled_model, minimum, free_gb, lambda: embeddings._openvino_model is not None
    )
    stop = threading.Event()
    threading.Thread(target=watch, args=(floor, free_gb, _abort, stop), daemon=True).start()
    sys.argv = ["eval.everyday_evaluation", "--capture"]
    try:
        runpy.run_module("eval.everyday_evaluation", run_name="__main__")
    except MemoryLow as error:
        print(f"[guard] ABORTED: {error}. Nothing was written.", flush=True)
        return ABORT_EXIT
    except SystemExit as done:
        return int(done.code or 0)
    finally:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
