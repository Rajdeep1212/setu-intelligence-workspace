import unittest
from unittest.mock import AsyncMock, patch

from app.clarification import focused_clarification
from app.schemas import QueryRequest
from pydantic import ValidationError


class ClarificationContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_reply_and_original_reach_graph_with_selected_language(self):
        from app.main import query
        original = "Where do I apply for the student credit card scheme?"
        payload = QueryRequest(query="  West Bengal  ", language="bn", clarification_context={"original_query": original})
        with patch("app.main.run_agent", AsyncMock(return_value={"answer": "safe", "citations": []})) as graph:
            await query(payload, session=None)
        graph.assert_awaited_once_with(None, original + "\n\nClarification reply:   West Bengal  ", language="bn")
        self.assertIsNone(focused_clarification(graph.call_args.args[1], "bn"))

    async def test_explicit_state_does_not_repeat_missing_state_question(self):
        self.assertIsNotNone(focused_clarification("Where do I apply for the student credit card scheme?"))
        for state in ("West Bengal", "Bihar", "Jharkhand"):
            self.assertIsNone(focused_clarification(f"How do I apply for the {state} student credit card?"))

    async def test_context_is_bounded_and_not_blank(self):
        for original in (" ", "x" * 2001):
            with self.assertRaises(ValidationError):
                QueryRequest(query="West Bengal", clarification_context={"original_query": original})

    async def test_insurance_choice_resolves_original_ambiguity(self):
        original = "I need insurance: PMJJBY or PMSBY?"
        self.assertIsNotNone(focused_clarification(original))
        self.assertIsNone(focused_clarification(original + "\n\nClarification reply: PMSBY"))

    async def test_clear_comparison_does_not_ask_user_to_choose(self):
        self.assertIsNone(focused_clarification("What is the difference between PMJJBY and PMSBY?"))

    async def test_student_card_clarifies_in_hindi_and_bengali(self):
        for question, language in (("स्टूडेंट क्रेडिट कार्ड के लिए आवेदन कैसे करूँ?", "hi"), ("স্টুডেন্ট ক্রেডিট কার্ডের জন্য কীভাবে আবেদন করব?", "bn")):
            self.assertIsNotNone(focused_clarification(question, language))
            self.assertIsNone(focused_clarification(question + "\n\nClarification reply: West Bengal", language))
