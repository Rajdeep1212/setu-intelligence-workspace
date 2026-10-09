"""M2.2: the everyday-use evaluation runs offline from saved retrieval results."""

from __future__ import annotations

import asyncio
import unittest
from collections import Counter

from eval import everyday_evaluation as ev

UDYAM = "https://wb.gov.in/government-schemes-details-udyam-registration.aspx"


def _case(**overrides):
    case = {
        "id": "t",
        "language": "en",
        "query": "How do I get Udyam registration?",
        "expected_status": "answered",
        "required_sections": ["direct_answer"],
        "evidence": [{"expected_urls": [UDYAM], "expected_passage_markers": ["no fees"], "expected_rank_max": 5}],
    }
    case.update(overrides)
    return case


def _hit(url=UDYAM, content="Easy online registration with no fees", score=0.9):
    return {"id": "c1", "url": url, "content": content, "rerank_score": score}


def _score(case, results):
    return asyncio.run(ev.score_case(case, results))


class CaseFileTests(unittest.TestCase):
    def test_twelve_cases_four_per_language_with_status_sections_and_evidence(self):
        cases = ev.load_cases()
        self.assertEqual(len({case["id"] for case in cases}), 12)
        self.assertEqual(Counter(case["language"] for case in cases), Counter(en=4, hi=4, bn=4))
        for case in cases:
            self.assertIn(case["expected_status"], ev.EXPECTED_STATUSES, case["id"])
            self.assertTrue(case["required_sections"], case["id"])
            self.assertTrue(set(case["required_sections"]) <= ev.SECTIONS, case["id"])
            self.assertTrue(case["evidence"], case["id"])

    @unittest.skipUnless(ev.RETRIEVAL_PATH.exists(), "retrieval results are not recorded yet: run --capture on the laptop (eval/README.md)")
    def test_every_case_has_saved_retrieval_results(self):
        saved = ev.load_retrieval()["results"]
        self.assertEqual(sorted(saved), sorted(case["id"] for case in ev.load_cases()))


class ScoringTests(unittest.TestCase):
    def test_evidence_needs_the_source_and_the_passage_in_the_saved_results(self):
        self.assertTrue(_score(_case(), [_hit()])["evidence"]["passed"])
        self.assertFalse(_score(_case(), [_hit(content="About the portal")])["evidence"]["passed"])
        self.assertFalse(_score(_case(), [_hit(url="https://example.gov.in/x")])["evidence"]["passed"])

    def test_a_question_with_evidence_is_handed_to_the_provider_which_is_never_called_for_an_answer(self):
        result = _score(_case(), [_hit()])
        self.assertEqual(result["status"]["observed"], ev.PROVIDER_DECIDES)
        self.assertTrue(result["status"]["passed"])
        # Provider-written sections carry no label today, so they cannot pass offline.
        self.assertFalse(result["sections"]["passed"])

    def test_code_decided_statuses_are_observed_without_a_provider(self):
        empty = _score(_case(expected_status="abstained", required_sections=["plain_abstention"], evidence=[{"expect_no_supported_item": True}]), [])
        self.assertEqual(empty["status"]["observed"], "abstained")
        self.assertTrue(empty["status"]["passed"] and empty["sections"]["passed"] and empty["evidence"]["passed"])
        personal = _score(_case(query="Am I eligible for PM Kisan?", expected_status="eligibility_unverified", required_sections=["eligibility_handoff"], evidence=[{"official_next_step": True}]), [_hit()])
        self.assertEqual(personal["status"]["observed"], "eligibility_unverified")
        self.assertTrue(personal["sections"]["passed"])

    def test_abstention_left_to_the_provider_is_not_counted_as_a_pass(self):
        result = _score(_case(expected_status="abstained", evidence=[{"expect_no_supported_item": True}]), [_hit(score=0.9)])
        self.assertFalse(result["status"]["passed"])
        self.assertFalse(result["evidence"]["passed"])
        self.assertFalse(result["passed"])


@unittest.skipUnless(ev.RETRIEVAL_PATH.exists(), "retrieval results are not recorded yet: run --capture on the laptop (eval/README.md)")
class BaselineTests(unittest.TestCase):
    def test_tracked_report_is_what_the_saved_results_produce_today(self):
        report = ev.evaluate()
        self.assertEqual(report["cases"], 12)
        self.assertEqual(report["activity_accounting"], {"provider_calls": 0, "database_requests": 0, "external_requests": 0, "model_downloads": 0})
        self.assertEqual(ev.REPORT_PATH.read_text(encoding="utf-8"), ev.markdown(report))


if __name__ == "__main__":
    unittest.main()
