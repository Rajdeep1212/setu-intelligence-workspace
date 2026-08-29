import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.agent import graph
from app.agent.models import GeneratedAnswer, RouteDecision
from app.grounding import abstention_message
from app.numerical_grounding import validate_numerical_grounding


def _chunk(content: str, chunk_id: str = "chunk-1") -> dict:
    return {
        "id": chunk_id,
        "document_id": "document-1",
        "content": content,
        "title": "Evidence",
        "url": None,
    }


def _state(content: str, language: str = "en") -> dict:
    return {
        "query": "What does the evidence support?",
        "language": language,
        "route": "retrieve_docs",
        "retrieved_chunks": [_chunk(content)],
    }


def _answer(text: str, citation_ids: list[str] | None = None) -> GeneratedAnswer:
    return GeneratedAnswer(
        answer=text,
        confidence=0.9,
        citation_ids=citation_ids or ["chunk-1"],
        abstained=False,
    )


class NumericalExpressionTests(unittest.TestCase):
    def assertGrounded(self, answer: str, evidence: str) -> None:
        result = validate_numerical_grounding(answer, [evidence])
        self.assertTrue(result.is_valid)
        self.assertGreater(result.expression_count, 0)
        self.assertEqual(result.unsupported_count, 0)

    def assertUnsupported(self, answer: str, evidence: str) -> None:
        result = validate_numerical_grounding(answer, [evidence])
        self.assertFalse(result.is_valid)
        self.assertGreater(result.unsupported_count, 0)

    def test_supported_and_unsupported_integer(self):
        self.assertGrounded("The programme serves 42 districts.", "It serves 42 districts.")
        self.assertUnsupported("The programme serves 42 districts.", "It serves 41 districts.")

    def test_supported_decimal_with_scale(self):
        self.assertGrounded("It serves 1.4 billion people.", "It serves 1.4 billion people.")

    def test_unsupported_decimal_scale_matches_en1_failure_family(self):
        self.assertUnsupported(
            "It operates at a scale of 1.4 billion people.",
            "It provides population-scale infrastructure.",
        )

    def test_comma_format_normalization(self):
        self.assertGrounded("There are 14,249 courts.", "There are 14249 courts.")
        self.assertGrounded("There are 1,40,000 accounts.", "There are 140000 accounts.")

    def test_percentage_requires_percentage_support(self):
        self.assertGrounded("Coverage reached 50%.", "Coverage reached 50 percent.")
        self.assertUnsupported("Coverage reached 51%.", "Coverage reached 50 percent.")

    def test_uuids_citation_ids_and_urls_are_ignored(self):
        answer = (
            "See [chunk_id=chunk-2024] "
            "548addec-36c6-4d9a-85e2-f3b406c5362d "
            "and https://example.test/reports/2026/42."
        )
        result = validate_numerical_grounding(answer, [])
        self.assertTrue(result.is_valid)
        self.assertEqual(result.expression_count, 0)

    def test_structural_list_numbering_is_ignored(self):
        result = validate_numerical_grounding(
            "1. First supported point.\n2) Second supported point.", []
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.expression_count, 0)

    def test_unicode_decimal_digits_are_normalized(self):
        self.assertGrounded("The programme delivered ২২০ crore doses.", "It delivered 220 crore doses.")

    def test_supported_numbers_in_all_supported_languages(self):
        cases = (
            ("It serves 25 districts.", "Evidence confirms 25 districts."),
            ("यह २५ जिलों में काम करता है।", "प्रमाण में 25 जिलों की पुष्टि है।"),
            ("এটি ২৫ জেলায় কাজ করে।", "প্রমাণে 25 জেলায় কাজের কথা আছে।"),
        )
        for answer, evidence in cases:
            with self.subTest(answer=answer):
                self.assertGrounded(answer, evidence)

    def test_material_scale_and_unit_must_match(self):
        self.assertUnsupported("It serves 42 districts.", "It operated for 42 days.")
        self.assertUnsupported("It serves 1.4 billion people.", "It spent 1.4 million dollars.")


class NumericalCorrectionPipelineTests(unittest.TestCase):
    def test_unsupported_number_is_removed_by_single_correction(self):
        first = _answer("The system serves 1.4 billion people.")
        corrected = _answer("The system supports public service delivery.")
        with (
            self.assertLogs("app.agent.graph", level="INFO") as captured,
            patch.object(
                graph, "generate_structured", side_effect=[first, corrected]
            ) as generate,
        ):
            update = asyncio.run(
                graph.generate_node(_state("Public service delivery is supported."))
            )

        self.assertEqual(generate.call_count, 2)
        self.assertEqual(update["answer"], corrected.answer)
        self.assertIn(
            "Every number", generate.call_args_list[1].kwargs["system_prompt"]
        )
        self.assertIn(
            "do not add remembered",
            generate.call_args_list[0].kwargs["system_prompt"],
        )
        self.assertIn(
            "Do not introduce a number",
            generate.call_args_list[0].kwargs["system_prompt"],
        )
        self.assertIn("answer_correction_succeeded", "\n".join(captured.output))

    def test_persistent_unsupported_number_returns_localized_abstention(self):
        outputs = [_answer("It serves 42 districts."), _answer("It serves 43 districts.")]
        state = _state("The programme serves citizens.")
        with patch.object(graph, "generate_structured", side_effect=outputs) as generate:
            update = asyncio.run(graph.generate_node(state))

        self.assertEqual(generate.call_count, 2)
        self.assertEqual(update["answer"], abstention_message(state["query"], "en"))
        self.assertEqual(update["confidence"], 0.0)
        self.assertEqual(update["citations"], [])

    def test_combined_language_and_number_failure_uses_only_one_correction(self):
        first = _answer("यह ४२ जिलों में काम करता है।")
        corrected = _answer("The programme supports public services.")
        with patch.object(
            graph, "generate_structured", side_effect=[first, corrected]
        ) as generate:
            update = asyncio.run(graph.generate_node(_state("Public services are supported.")))

        self.assertEqual(generate.call_count, 2)
        self.assertEqual(update["answer"], corrected.answer)

    def test_route_and_retrieval_run_once_and_answer_generation_at_most_twice(self):
        route = RouteDecision(route="retrieve_docs", scheme_name_hint=None)
        first = _answer("It serves 42 districts.")
        corrected = _answer("It supports public services.")
        retrieve = AsyncMock(return_value=[_chunk("Public services are supported.")])
        session = object()
        with (
            patch.object(
                graph, "generate_structured", side_effect=[route, first, corrected]
            ) as generate,
            patch.object(graph, "retrieve_docs_tool", retrieve),
        ):
            result = asyncio.run(
                graph.run_agent(session, "What is supported?", language="en")
            )

        stages = [call.kwargs["stage"] for call in generate.call_args_list]
        self.assertEqual(stages.count("route_decision"), 1)
        self.assertEqual(stages.count("answer_generation"), 2)
        retrieve.assert_awaited_once_with(session, "What is supported?", "en")
        self.assertEqual(result["answer"], corrected.answer)

    def test_citations_remain_allowlisted_during_numeric_correction(self):
        state = _state("The programme supports citizens.")
        first = _answer("It serves 42 citizens.", ["fabricated", "chunk-1"])
        corrected = _answer("The programme supports citizens.", ["fabricated", "chunk-1"])
        with patch.object(
            graph, "generate_structured", side_effect=[first, corrected]
        ) as generate:
            update = asyncio.run(graph.generate_node(state))

        self.assertEqual(generate.call_count, 2)
        self.assertEqual(
            [citation["chunk_id"] for citation in update["citations"]], ["chunk-1"]
        )

    def test_logs_expose_only_safe_numeric_validation_metadata(self):
        answer_secret = "ANSWER_SECRET serves 987654 districts."
        evidence_secret = "EVIDENCE_SECRET serves 123456 districts."
        prompt_secret = "PROMPT_SECRET_do_not_log"
        state = _state(evidence_secret)
        state["query"] = prompt_secret
        outputs = [_answer(answer_secret), _answer(answer_secret)]
        with (
            self.assertLogs("app.agent.graph", level="WARNING") as captured,
            patch.object(graph, "generate_structured", side_effect=outputs),
        ):
            update = asyncio.run(graph.generate_node(state))

        self.assertEqual(update["citations"], [])
        logs = "\n".join(captured.output)
        self.assertIn("unsupported_count=1", logs)
        for sensitive in (
            answer_secret,
            evidence_secret,
            prompt_secret,
            "987654",
            "123456",
            "API_KEY_SECRET",
            "Authorization",
        ):
            self.assertNotIn(sensitive, logs)


if __name__ == "__main__":
    unittest.main()
