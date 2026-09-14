"""Loopback-only Uvicorn entry point for the connected browser gate."""

from __future__ import annotations

import os
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
settings.setu_api_key = integration_api_key()
app.dependency_overrides[get_session] = harness.get_session
_provider_patch = patch(
    "app.agent.graph.generate_structured",
    side_effect=harness.generate_structured,
)
_provider_patch.start()

# Compile the existing local models before Uvicorn reports the temporary test
# server ready.  This keeps cold model construction outside the BFF request;
# retrieval and reranking still execute normally for every browser question.
_get_openvino_model()
_get_reranker()
