from __future__ import annotations

import importlib.metadata
import json
import os
import time
import unittest
from unittest.mock import patch

import langgraph
import langgraph.graph
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_session
from app.language import answer_uses_target_language
from app.main import app
from tests.real_runtime_support import (
    EXPECTED_COUNTS,
    RealRuntimeHarness,
    integration_api_key,
)


@unittest.skipUnless(
    os.environ.get("SETU_REAL_STAGING_INTEGRATION") == "1",
    "set SETU_REAL_STAGING_INTEGRATION=1 for the read-only staging gate",
)
class RealRuntimeStagingJourneyTests(unittest.TestCase):
    """Real runtime and staging retrieval with deterministic provider boundary."""

    @classmethod
    def setUpClass(cls):
        package_paths = [str(path) for path in langgraph.__path__]
        graph_path = str(langgraph.graph.__file__)
        if any("tests" in path or "langgraph_test_stub" in path for path in package_paths + [graph_path]):
            raise RuntimeError("The installed LangGraph package was replaced by a test stub")
        cls.langgraph_proof = {
            "version": importlib.metadata.version("langgraph"),
            "package_paths": package_paths,
            "graph_path": graph_path,
        }
        cls.harness = RealRuntimeHarness()
        cls.old_api_key = settings.setu_api_key
        settings.setu_api_key = integration_api_key()
        app.dependency_overrides[get_session] = cls.harness.get_session
        cls.provider_patch = patch(
            "app.agent.graph.generate_structured",
            side_effect=cls.harness.generate_structured,
        )
        cls.provider_patch.start()
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.portal.call(cls.harness.engine.dispose)
        cls.client_context.__exit__(None, None, None)
        cls.provider_patch.stop()
        app.dependency_overrides.pop(get_session, None)
        settings.setu_api_key = cls.old_api_key

    def test_five_representative_journeys(self):
        journeys = [
            {
                "id": "clear_english",
                "query": "How do I register for e-Shram and what do I need?",
                "language": "en",
                "status": "answered",
                "provider_calls": 2,
                "expected_link_kinds": ["application", "help"],
            },
            {
                "id": "ambiguous_scheme",
                "query": "Where do I apply for the student credit card scheme?",
                "language": "en",
                "status": "clarification_needed",
                "provider_calls": 0,
                "expected_link_kinds": [],
            },
            {
                "id": "hindi",
                "query": "प्रधानमंत्री उज्ज्वला योजना के लिए आवेदन कैसे करूँ और कौन से दस्तावेज़ चाहिए?",
                "language": "hi",
                "status": "answered",
                "provider_calls": 2,
                "expected_link_kinds": [],
            },
            {
                "id": "bengali",
                "query": "পশ্চিমবঙ্গ স্টুডেন্ট ক্রেডিট কার্ডের জন্য কীভাবে আবেদন করব?",
                "language": "bn",
                "status": "answered",
                "provider_calls": 2,
                "expected_link_kinds": ["application", "help"],
            },
            {
                "id": "unsupported_amount",
                "query": "ई-श्रम कार्ड बनते ही ₹3,000 मिलते हैं ना?",
                "language": "hi",
                "status": "abstained",
                "provider_calls": 1,
                "expected_link_kinds": [],
            },
        ]
        results = []

        journey_filter = os.environ.get("SETU_REAL_JOURNEY_FILTER")
        selected_journeys = [
            journey
            for journey in journeys
            if journey_filter in {None, "", journey["id"]}
        ]
        if not selected_journeys:
            self.fail("SETU_REAL_JOURNEY_FILTER did not match a journey")

        for journey in selected_journeys:
            with self.subTest(journey=journey["id"]):
                before = self.harness.provider_calls[journey["query"]]
                started = time.perf_counter()
                response = self.client.post(
                    "/query",
                    json={"query": journey["query"], "language": journey["language"]},
                    headers={
                        "X-API-Key": settings.setu_api_key.get_secret_value()
                    },
                )
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                calls = self.harness.provider_calls[journey["query"]] - before
                self.assertEqual(calls, journey["provider_calls"])
                self.assertEqual(body["route"], "retrieve_docs")
                self.assertEqual(body["response_status"], journey["status"])
                self.assertTrue(
                    answer_uses_target_language(body["answer"], journey["language"])
                )
                self.assertNotIn("Aadhaar number?", body["answer"])
                self.assertNotIn("bank details?", body["answer"])
                self.assertEqual(
                    [link["kind"] for link in body["official_links"]],
                    journey["expected_link_kinds"],
                )
                for link in body["official_links"]:
                    self.assertTrue(link["url"].startswith(("http://", "https://")))

                record = self.harness.provider_records.get(journey["query"])
                if journey["provider_calls"] == 2:
                    self.assertIsNotNone(record)
                    citation_ids = [item["chunk_id"] for item in body["citations"]]
                    self.assertEqual(citation_ids, [record["chunk_id"]])
                    self.assertTrue(set(citation_ids) <= self.harness.staging_chunk_ids)
                    self.assertTrue(body["sections"])
                    for section in body["sections"]:
                        self.assertTrue(section["text"].strip())
                        self.assertTrue(set(section["citation_ids"]) <= set(citation_ids))
                elif journey["provider_calls"] == 0:
                    self.assertIsNone(record)
                    self.assertEqual(body["citations"], [])
                    self.assertEqual(body["official_links"], [])
                    self.assertEqual(len(body["sections"]), 1)
                    self.assertEqual(body["sections"][0]["citation_ids"], [])
                else:
                    self.assertEqual(journey["id"], "unsupported_amount")
                    self.assertIsNone(record)
                    self.assertEqual(body["citations"], [])
                    self.assertEqual(body["sections"], [])
                    self.assertEqual(body["official_links"], [])

                results.append(
                    {
                        "id": journey["id"],
                        "question": journey["query"],
                        "language": journey["language"],
                        "route": body["route"],
                        "status": body["response_status"],
                        "path": (
                            "clarification"
                            if journey["provider_calls"] == 0
                            else "retrieval_abstention_before_generation"
                            if journey["provider_calls"] == 1
                            else "retrieval_generation"
                        ),
                        "source": body["citations"][0]["url"] if body["citations"] else None,
                        "useful_passage_rank": record["useful_passage_rank"] if record else None,
                        "citation_chunk_ids": [item["chunk_id"] for item in body["citations"]],
                        "section_kinds": [item.get("kind") for item in body["sections"]],
                        "official_links": body["official_links"],
                        "provider_double_calls": calls,
                        "local_latency_ms": latency_ms,
                    }
                )

        self.assertTrue(self.harness.database_observations)
        self.assertTrue(
            all(item["counts"] == EXPECTED_COUNTS for item in self.harness.database_observations)
        )
        print("REAL_LANGGRAPH=" + json.dumps(self.langgraph_proof, ensure_ascii=False))
        print("REAL_RUNTIME_JOURNEYS=" + json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
