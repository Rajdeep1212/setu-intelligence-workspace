import unittest

from eval.everyday_use_evaluation import evaluate


class EverydayUseEvaluationTests(unittest.TestCase):
    def test_balanced_reviewed_cases_have_passed_evidence_checkpoints(self):
        report = evaluate()
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["cases"], 12)
        self.assertEqual(report["by_language"], {"en": 4, "hi": 4, "bn": 4})
        self.assertEqual(report["source_passage_checks_passed"], 12)
        self.assertEqual(report["retrieval_checkpoints_passed"], 12)
        self.assertEqual(
            report["activity"],
            {"provider_calls": 0, "database_requests": 0, "external_requests": 0},
        )


if __name__ == "__main__":
    unittest.main()
