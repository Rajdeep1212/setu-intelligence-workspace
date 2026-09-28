import threading
import unittest
from collections import Counter

from app.agent.models import GeneratedAnswer
from app.language import target_language_instruction
from tests.real_runtime_support import RealRuntimeHarness


class DeterministicProviderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.harness = object.__new__(RealRuntimeHarness)
        self.harness._lock = threading.Lock()
        self.harness.provider_calls = Counter()
        self.harness.provider_records = {}

    def test_pmsby_answer_uses_returned_bank_account_eligibility_passage(self):
        query = "PMSBY के लिए कौन पात्र है?"
        passage = (
            "### Which Bank Accounts are eligible for subscribing to PMSBY?\n\n"
            "All bank account holders other than institutional account holders "
            "are eligible for subscribing to PMSBY scheme."
        )
        result = self.harness.generate_structured(
            stage="answer_generation",
            system_prompt=target_language_instruction("hi"),
            user_prompt=f"Context:\n[chunk_id=bank-eligibility]\n{passage}\n\nQuestion: {query}",
            response_model=GeneratedAnswer,
        )

        self.assertEqual(result.citation_ids, ["bank-eligibility"])
        self.assertIn("संस्थागत खाताधारकों को छोड़कर", result.answer)
        self.assertNotIn("18", result.answer)


if __name__ == "__main__":
    unittest.main()
