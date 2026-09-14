from __future__ import annotations

import asyncio
import hashlib
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.agent.graph import run_agent
from app.schemas import QueryRequest
from tests.real_runtime_support import RealRuntimeHarness


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class QuestionBoundaryTests(unittest.TestCase):
    def test_fastapi_graph_and_provider_parser_preserve_the_exact_question(self):
        exact = "How do I register for e-Shram and what do I need?"
        parsed = QueryRequest(query=exact, language="en")
        harness = RealRuntimeHarness()
        evidence = {
            "id": "diagnostic-chunk",
            "document_id": "diagnostic-document",
            "content": "Aadhaar linked Mobile number and bank account details are required.",
            "language": "en",
            "title": "Diagnostic evidence",
            "source": "Test",
            "url": None,
            "rerank_score": 0.9,
            "document_metadata": {},
        }

        with (
            patch(
                "app.agent.graph.retrieve_docs_tool",
                new=AsyncMock(return_value=[evidence]),
            ),
            patch(
                "app.agent.graph.generate_structured",
                side_effect=harness.generate_structured,
            ),
        ):
            result = asyncio.run(run_agent(object(), parsed.query, language=parsed.language))
        asyncio.run(harness.engine.dispose())

        route_seen = harness.provider_calls[exact] >= 1
        answer_record = harness.provider_records[exact]
        diagnostics = [
            {"boundary": "fastapi_query_request", "length": len(parsed.query), "fingerprint": _fingerprint(parsed.query), "equals_fixture": parsed.query == exact},
            {"boundary": "graph_route_prompt", "length": len(exact), "fingerprint": _fingerprint(exact), "equals_fixture": route_seen},
            {"boundary": "provider_answer_parser", "length": len(exact), "fingerprint": _fingerprint(exact), "equals_fixture": answer_record["language"] == "en"},
        ]
        print("QUESTION_BOUNDARIES=" + json.dumps(diagnostics))
        self.assertEqual(result["response_status"], "answered")
        self.assertTrue(all(item["equals_fixture"] for item in diagnostics))


if __name__ == "__main__":
    unittest.main()
