"""
Retrieval precision@k — Week 2.

Reads eval/eval_set.jsonl (see eval/README.md for the format and how to
build it), runs each query through the same hybrid retrieval pipeline
/query uses, and reports precision@k overall and per language.

Run from the repo root:
    python -m eval.precision_at_k
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.db import AsyncSessionLocal
from app.retrieval.pipeline import retrieve

EVAL_SET_PATH = Path(__file__).parent / "eval_set.jsonl"


def _load_eval_set() -> list[dict]:
    if not EVAL_SET_PATH.exists() or not EVAL_SET_PATH.read_text().strip():
        return []
    return [
        json.loads(line)
        for line in EVAL_SET_PATH.read_text().splitlines()
        if line.strip()
    ]


async def precision_at_k(k: int = 5) -> None:
    rows = _load_eval_set()
    if not rows:
        print(
            f"No eval rows found at {EVAL_SET_PATH}.\n"
            "See eval/README.md for the format and how to build one from "
            "your ingested chunks."
        )
        return

    per_language: dict[str, list[float]] = {}
    overall: list[float] = []

    async with AsyncSessionLocal() as session:
        for row in rows:
            results = await retrieve(session, row["query"], row.get("language"), final_k=k)
            retrieved_ids = {r["id"] for r in results}
            relevant_ids = set(row["relevant_chunk_ids"])

            hits = len(retrieved_ids & relevant_ids)
            precision = hits / k

            overall.append(precision)
            lang = row.get("language", "unknown")
            per_language.setdefault(lang, []).append(precision)

    print(f"Overall precision@{k}: {sum(overall) / len(overall):.3f}  (n={len(overall)})")
    print("Per language:")
    for lang, scores in sorted(per_language.items()):
        print(f"  {lang}: {sum(scores) / len(scores):.3f}  (n={len(scores)})")

    print(
        "\nTarget from the original plan: precision@5 >= 0.80 overall — "
        "check the per-language numbers too, a good aggregate can hide a "
        "weak language."
    )


if __name__ == "__main__":
    asyncio.run(precision_at_k())
