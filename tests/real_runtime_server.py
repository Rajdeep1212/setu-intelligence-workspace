"""Loopback-only Uvicorn entry point for the connected browser gate."""

from __future__ import annotations

import os
import time
import hashlib
import importlib.metadata
from pathlib import Path
from unittest.mock import patch

if os.environ.get("SETU_REAL_STAGING_INTEGRATION") != "1":
    raise RuntimeError("This test-only server requires explicit staging opt-in")

from app.config import settings
from app.db import get_session
from app.main import app
from app.retrieval.embeddings import _get_openvino_model
from app.retrieval.rerank import _get_reranker
from tests.real_runtime_support import RealRuntimeHarness, integration_api_key


if settings.local_inference_backend != "openvino":
    raise RuntimeError("The connected staging gate requires the local OpenVINO backend")

harness = RealRuntimeHarness()
source_root = Path(__file__).resolve().parents[1]
loaded_source_hashes = {
    name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
    for name in (
        "app/config.py", "app/main.py", "app/schemas.py", "app/clarification.py",
        "app/agent/graph.py", "app/retrieval/pipeline.py",
        "app/retrieval/openvino_backend.py", "app/retrieval/rerank.py",
        "app/numerical_grounding.py",
        "tests/real_runtime_server.py", "tests/real_runtime_support.py",
    )
}
settings.setu_api_key = integration_api_key()
app.dependency_overrides[get_session] = harness.get_session
_provider_patch = patch(
    "app.agent.graph.generate_structured",
    side_effect=harness.generate_structured,
)
_provider_patch.start()

# Fail closed if a code path accidentally bypasses the deterministic boundary.
# Database traffic uses asyncpg, not HTTPX; real inbound HTTP remains untouched.
_http_sync_patch = patch("httpx.Client.send", side_effect=AssertionError("Outbound HTTP disabled in staging verification"))
_http_async_patch = patch("httpx.AsyncClient.send", side_effect=AssertionError("Outbound HTTP disabled in staging verification"))
_http_sync_patch.start()
_http_async_patch.start()

@app.get("/__test/evidence")
async def evidence():
    compiled = reranker.compiled_model
    return {
        "provider_records": harness.provider_records,
        "provider_calls": dict(harness.provider_calls),
        "database_observations": harness.database_observations,
        "pool_checked_out": harness.engine.sync_engine.pool.checkedout(),
        "startup_seconds": startup_seconds,
        "loaded_source_hashes": loaded_source_hashes,
        "langgraph_version": importlib.metadata.version("langgraph"),
        "inference_configuration": {
            "backend": settings.local_inference_backend,
            "precision": str(compiled.get_property("INFERENCE_PRECISION_HINT")),
            "performance_hint": str(compiled.get_property("PERFORMANCE_HINT")),
            "streams": int(compiled.get_property("NUM_STREAMS")),
            "threads": int(compiled.get_property("INFERENCE_NUM_THREADS")),
            "hyperthreading": bool(compiled.get_property("ENABLE_HYPER_THREADING")),
        },
    }

# Compile the existing local models before Uvicorn reports the temporary test
# server ready.  This keeps cold model construction outside the BFF request;
# retrieval and reranking still execute normally for every browser question.
startup_started = time.perf_counter()
embedding_model = _get_openvino_model()
reranker = _get_reranker()
startup_seconds = time.perf_counter() - startup_started
