"""P6: official next steps come only from the reviewed table, by fixed rules.

Offline tests. The API test patches the agent; nothing reaches a model,
database or network.
"""

import importlib
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import next_steps
from app.agent import graph
from app.schemas import QueryResponse

main = importlib.import_module("app.main")
security = importlib.import_module("app.security")
AUTH_HEADERS = {"X-API-Key": "unit-test-api-key"}


class _Session:
    async def execute(self, _):
        class _Result:
            def scalar(self):
                return 1

        return _Result()


async def _fake_session():
    yield _Session()


class TableTests(unittest.TestCase):
    def test_every_service_is_official_https_and_checked(self):
        table = json.loads(next_steps.SERVICES_PATH.read_text(encoding="utf-8"))
        for service_id, service in table["services"].items():
            with self.subTest(service=service_id):
                self.assertTrue(next_steps.is_official_url(service["url"]), service["url"])
                self.assertRegex(service["verified_on"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(service["verified_by"].strip())
                self.assertTrue(service["operator"].strip())
                self.assertEqual(set(service["label"]), set(next_steps.LANGUAGES))

    def test_official_url_rule_rejects_look_alikes_and_plain_http(self):
        for url in (
            "https://pmkisan.app/status",
            "https://pmkisann.com/",
            "https://pmkisan.gov.in.example.com/",
            "http://pmkisan.gov.in/",
            "https://echallan-parivahan.online/",
        ):
            with self.subTest(url=url):
                self.assertFalse(next_steps.is_official_url(url))

    def test_table_loads_and_rules_refer_to_known_services(self):
        next_steps.load_table.cache_clear()
        self.assertIn("myscheme", next_steps.load_table()["services"])


class SelectionTests(unittest.TestCase):
    def test_answered_and_abstained_responses_carry_no_steps(self):
        for status in ("answered", "abstained", None):
            with self.subTest(status=status):
                self.assertEqual(next_steps.select(status, "What is PM-KISAN?", "en"), [])

    def test_eligibility_question_names_the_scheme_portal_when_the_scheme_is_named(self):
        for query, language in (
            ("Am I eligible for PM-KISAN?", "en"),
            ("क्या मैं पीएम-किसान के लिए पात्र हूँ?", "hi"),
            ("আমি কি পিএম-কিষাণের যোগ্য?", "bn"),
        ):
            with self.subTest(language=language):
                steps = next_steps.select("eligibility_unverified", query, language)
                self.assertEqual([step["id"] for step in steps], ["pmkisan_status", "myscheme"])
        other = next_steps.select("eligibility_unverified", "Am I eligible for the scholarship?", "en")
        self.assertEqual([step["id"] for step in other], ["myscheme"])

    def test_labels_are_in_the_answer_language(self):
        steps = next_steps.select("eligibility_unverified", "क्या मैं पात्र हूँ?", "hi")
        self.assertRegex(steps[0]["label"], r"[ऀ-ॿ]")
        fallback = next_steps.select("eligibility_unverified", "Am I eligible?", "ta")
        self.assertRegex(fallback[0]["label"], r"^[A-Za-z]")

    def test_scam_and_traffic_rules_are_ready_for_their_routes(self):
        self.assertEqual([s["id"] for s in next_steps.select("scam_check", "Pay challan at bit.ly/x", "en")], ["cybercrime", "echallan"])
        self.assertEqual([s["id"] for s in next_steps.select("scam_check", "Free laptop scheme", "en")], ["cybercrime"])
        self.assertEqual([s["id"] for s in next_steps.select("rule_lookup", "Helmet fine Kolkata", "en")], ["echallan", "digilocker"])

    def test_every_selected_step_is_on_the_reviewed_list(self):
        table = next_steps.load_table()
        allowed = {service["url"] for service in table["services"].values()}
        for rule in table["rules"]:
            for language in next_steps.LANGUAGES:
                for step in next_steps.select(rule["when"]["response_status"], "PM-KISAN challan", language):
                    self.assertIn(step["url"], allowed)
                    self.assertLessEqual(len(step), 4)


class ApiTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides[main.get_session] = _fake_session
        self.original_api_key = main.settings.setu_api_key
        self.original_limiter = security.query_rate_limiter
        main.settings.setu_api_key = SecretStr("unit-test-api-key")
        security.query_rate_limiter = security.InMemoryRateLimiter(1_000, 60)

    def tearDown(self):
        main.app.dependency_overrides.clear()
        main.settings.setu_api_key = self.original_api_key
        security.query_rate_limiter = self.original_limiter

    def _post(self, state, query):
        with patch.object(main, "run_agent", AsyncMock(return_value=state)), TestClient(main.app) as client:
            return client.post("/query", json={"query": query}, headers=AUTH_HEADERS)

    def test_eligibility_quarantine_response_now_links_the_official_portal(self):
        message = graph.ELIGIBILITY_UNVERIFIED_MESSAGES["en"]
        state = {
            "answer": message,
            "citations": [],
            "sections": [{"text": message, "citation_ids": []}],
            "route": "check_eligibility",
            "confidence": None,
            "response_status": "eligibility_unverified",
        }
        response = self._post(state, "Am I eligible for PM-KISAN?")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["response_status"], "eligibility_unverified")
        self.assertEqual([step["url"] for step in body["next_steps"]], [
            "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx",
            "https://www.myscheme.gov.in/",
        ])
        # The quarantine is unchanged: no decision, no criteria.
        self.assertNotRegex(body["answer"], r"(?i)\byou are (not )?eligible\b")

    def test_ordinary_answer_has_an_empty_list(self):
        state = {"answer": "Mocked answer.", "citations": [], "route": "retrieve_docs", "confidence": 1.0}
        body = self._post(state, "What is PM-KISAN?").json()
        self.assertEqual(body["next_steps"], [])

    def test_schema_caps_the_number_of_steps(self):
        step = {"id": "x", "label": "x", "url": "https://x.gov.in/", "operator": "x"}
        with self.assertRaises(ValueError):
            QueryResponse(answer="a", next_steps=[step] * 4)


if __name__ == "__main__":
    unittest.main()
