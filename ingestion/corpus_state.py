"""Resumable run state for one corpus batch (M2.1).

Kept in corpus/staging/<batch>/state.json, next to the downloaded snapshots,
and never tracked: the reviewed manifest stays exactly as a person left it.

Per source the stages only move forward:

    discovered -> fetched -> extracted -> validated -> chunked -> embedded -> indexed

``changed`` is a hold, not a stage: the fetched content no longer matches the
manifest pin, so a person must re-read the source and update the pin before
it can go further. Updating the pin resets the source to ``discovered``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STAGES = ("discovered", "fetched", "extracted", "validated", "chunked", "embedded", "indexed")
CHANGED = "changed"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RunState:
    def __init__(self, path: Path, batch_id: str, sources: dict[str, dict[str, Any]]):
        self.path = path
        self.batch_id = batch_id
        self.sources = sources

    @classmethod
    def load(cls, path: str | Path, batch_id: str) -> "RunState":
        state_path = Path(path)
        if not state_path.is_file():
            return cls(state_path, batch_id, {})
        data = json.loads(state_path.read_text(encoding="utf-8"))
        if data.get("batch_id") != batch_id:
            raise ValueError(f"{state_path.name} belongs to batch {data.get('batch_id')!r}, not {batch_id!r}")
        return cls(state_path, batch_id, data.get("sources", {}))

    def source(self, source_id: str) -> dict[str, Any]:
        return self.sources.setdefault(source_id, {"stage": "discovered", "attempts": 0, "last_error": None})

    def advance(self, source_id: str, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"Unknown stage {stage!r}")
        record = self.source(source_id)
        current = record["stage"]
        if current != CHANGED and STAGES.index(stage) < STAGES.index(current):
            raise ValueError(f"{source_id}: cannot move back from {current} to {stage}")
        record["stage"] = stage
        record[f"{stage}_at"] = utc_now()
        record["last_error"] = None

    def hold_changed(self, source_id: str, reason: str) -> None:
        record = self.source(source_id)
        record["stage"] = CHANGED
        record["last_error"] = reason

    def fail(self, source_id: str, error: BaseException) -> None:
        self.source(source_id)["last_error"] = f"{type(error).__name__}: {error}"

    def reset(self, source_id: str) -> dict[str, Any]:
        attempts = self.source(source_id)["attempts"]
        self.sources[source_id] = {"stage": "discovered", "attempts": attempts, "last_error": None}
        return self.sources[source_id]

    def at_least(self, source_id: str, stage: str) -> bool:
        current = self.source(source_id)["stage"]
        return current != CHANGED and STAGES.index(current) >= STAGES.index(stage)

    def counts(self) -> dict[str, int]:
        counts = {stage: 0 for stage in (*STAGES, CHANGED)}
        for record in self.sources.values():
            counts[record["stage"]] += 1
        return counts

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.part")
        payload = {"batch_id": self.batch_id, "updated_at": utc_now(), "sources": self.sources}
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
