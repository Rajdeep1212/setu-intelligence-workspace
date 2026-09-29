import unittest

from eval.temporal_evaluation import CATEGORIES, LANGUAGES, evaluate, load_cases


class TemporalSuiteTests(unittest.TestCase):
    def test_cases_are_balanced_and_marked_by_phase(self):
        cases = load_cases()

        self.assertEqual(len(cases), 15)
        for language in LANGUAGES:
            self.assertEqual(sum(case["language"] == language for case in cases), 5)
        self.assertTrue({case["category"] for case in cases} <= set(CATEGORIES))
        # Phase 1 (temporal_retrieval) and Phase 3 (missing_facts, false_premise) are done.
        for case in cases:
            self.assertEqual(case["expected_status"], "pass", case["id"])
            self.assertNotIn("xfail_reason", case)

    def test_outcomes_match_markings_without_external_activity(self):
        report, success = evaluate()

        self.assertTrue(success, report["unexpected"] or report["fixture_errors"] or report["manifest_errors"])
        self.assertEqual(report["outcomes"], {"pass": 15})
        self.assertEqual(report["by_category"]["temporal_retrieval"], {"pass": 6})
        self.assertEqual(report["by_category"]["missing_facts"], {"pass": 3})
        self.assertEqual(report["by_category"]["false_premise"], {"pass": 6})
        self.assertEqual(
            report["activity_accounting"],
            {"provider_calls": 0, "database_requests": 0, "external_requests": 0, "model_downloads": 0},
        )


if __name__ == "__main__":
    unittest.main()
