"""Verify readiness can acquire the one-connection staging pool during reranking."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import patch

from app.retrieval.pipeline import retrieve
from tests.real_runtime_support import EXPECTED_COUNTS, RealRuntimeHarness


async def main() -> int:
    harness = RealRuntimeHarness()
    query_dependency = harness.get_session()
    readiness_dependency = None
    release_reranker = threading.Event()
    reranker_started = threading.Event()
    query_task = None

    def paused_reranker(_query, candidates, *, top_k):
        reranker_started.set()
        if not release_reranker.wait(timeout=10):
            raise TimeoutError("readiness probe did not release reranker")
        return candidates[:top_k]

    try:
        query_session = await anext(query_dependency)
        with (
            patch(
                "app.retrieval.pipeline.embed_chunks",
                return_value=[[0.0] * 1024],
            ),
            patch(
                "app.retrieval.pipeline.rerank",
                side_effect=paused_reranker,
            ),
        ):
            query_task = asyncio.create_task(
                retrieve(query_session, "readiness contention probe", language="en")
            )
            started = await asyncio.to_thread(reranker_started.wait, 5)
            if not started:
                raise TimeoutError("retrieval did not reach reranking")

            readiness_dependency = harness.get_session()
            ready_started = time.perf_counter()
            await asyncio.wait_for(anext(readiness_dependency), timeout=5)
            ready_ms = (time.perf_counter() - ready_started) * 1000
            release_reranker.set()
            results = await query_task

        counts_ok = bool(harness.database_observations) and all(
            observation["counts"] == EXPECTED_COUNTS
            for observation in harness.database_observations
        )
        pool_idle = harness.engine.pool.checkedout() == 0
        passed = bool(results) and counts_ok and pool_idle
        print(
            "READINESS_CONTENTION_PROBE "
            f"pool_size=1 ready_during_rerank=true ready_ms={ready_ms:.2f} "
            f"counts_ok={str(counts_ok).lower()} "
            f"pool_checked_out={harness.engine.pool.checkedout()} "
            f"passed={str(passed).lower()}"
        )
        return 0 if passed else 1
    finally:
        release_reranker.set()
        if query_task is not None and not query_task.done():
            await query_task
        if readiness_dependency is not None:
            await readiness_dependency.aclose()
        await query_dependency.aclose()
        await harness.engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
