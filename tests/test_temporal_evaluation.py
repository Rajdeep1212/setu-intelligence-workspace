import unittest

from eval.temporal_evaluation import CATEGORIES, LANGUAGES, evaluate, load_cases


class TemporalExpectedFailureSuiteTests(unittest.TestCase):
    def test_cases_are_balanced_and_marked_expected_to_fail(self):
        cases = load_cases()

        self.assertEqual(len(cases), 15)
        for language in LANGUAGES:
            self.assertEqual(sum(case["language"] == language for case in cases), 5)
        self.assertTrue({case["category"] for case in cases} <= set(CATEGORIES))
        self.assertTrue(all(case["expected_status"] == "xfail" and case["xfail_reason"] for case in cases))

    def test_every_case_currently_fails_as_expected_without_external_activity(self):
        report, success = evaluate()

        self.assertTrue(success, report["unexpected"] or report["fixture_errors"] or report["manifest_errors"])
        self.assertEqual(report["outcomes"], {"xfail": 15})
        self.assertEqual(
            report["activity_accounting"],
            {"provider_calls": 0, "database_requests": 0, "external_requests": 0, "model_downloads": 0},
        )


if __name__ == "__main__":
    unittest.main()
