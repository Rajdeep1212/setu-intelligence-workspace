import json
import unittest

from eval.offline_evaluation import EVAL_DIR, corpus_fingerprint, evaluate, load_jsonl


class OfflineEvaluationTests(unittest.TestCase):
    def test_manifest_declares_60_unique_balanced_cases(self):
        manifest = json.loads((EVAL_DIR / "offline_manifest.json").read_text(encoding="utf-8"))
        cases = load_jsonl(EVAL_DIR / "offline_cases.jsonl")

        self.assertEqual(len(cases), 60)
        self.assertEqual(len({case["id"] for case in cases}), 60)
        self.assertEqual(manifest["case_counts_by_language"], {"en": 20, "hi": 20, "bn": 20})
        self.assertEqual(sum(manifest["case_counts_by_category"].values()), 60)

    def test_corpus_fingerprint_matches_reviewed_manifest(self):
        manifest = json.loads((EVAL_DIR / "offline_manifest.json").read_text(encoding="utf-8"))
        actual = corpus_fingerprint(
            load_jsonl(EVAL_DIR / "eval_set.jsonl"),
            load_jsonl(EVAL_DIR / "grounding_set.jsonl"),
        )

        self.assertEqual(actual, manifest["corpus_fingerprint"]["value"])

    def test_complete_evaluation_passes_without_external_activity(self):
        report, success = evaluate()

        self.assertTrue(success, report)
        self.assertEqual(report["headline_unique_cases"], 60)
        self.assertEqual(report["passed"], 60)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(
            report["activity_accounting"],
            {
                "provider_calls": 0,
                "database_requests": 0,
                "external_requests": 0,
                "model_downloads": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
