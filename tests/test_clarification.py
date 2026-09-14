import unittest

from app.clarification import focused_clarification
from app.schemas import QueryRequest


class FocusedClarificationTests(unittest.TestCase):
    def test_clear_scheme_and_jurisdiction_proceeds(self):
        self.assertIsNone(
            focused_clarification(
                "Where do I apply for the West Bengal Student Credit Card?",
                "en",
            )
        )

    def test_missing_jurisdiction_gets_one_english_question(self):
        self.assertEqual(
            focused_clarification(
                "Where do I apply for the student credit card scheme?", "en"
            ),
            "Which state or Union Territory's student credit card scheme do you mean?",
        )

    def test_similar_scheme_names_get_one_hindi_question(self):
        self.assertEqual(
            focused_clarification(
                "मुझे बीमा योजना चाहिए—PMJJBY या PMSBY?", "hi"
            ),
            "क्या आपको PMJJBY का जीवन बीमा चाहिए या PMSBY का दुर्घटना बीमा?",
        )

    def test_generic_pension_gets_one_bengali_question(self):
        self.assertEqual(
            focused_clarification(
                "বয়স্ক পেনশনের জন্য কোথায় আবেদন করব?", "bn"
            ),
            "কোন রাজ্য বা কেন্দ্রশাসিত অঞ্চল প্রযোজ্য, এবং আপনি কোন বার্ধক্য পেনশন প্রকল্পের কথা বলছেন?",
        )

    def test_unknown_scheme_is_not_guessed_or_blocked_by_narrow_guard(self):
        self.assertIsNone(focused_clarification("What is Andhan Nirudhana?", "en"))

    def test_request_validation_preserves_exact_question(self):
        question = "  Where do I apply for e-Shram?  "
        self.assertEqual(QueryRequest(query=question, language="en").query, question)


if __name__ == "__main__":
    unittest.main()
