import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.agent import graph
from app.agent.models import GeneratedAnswer, RouteDecision
from app.grounding import abstention_message
from app.language import (
    answer_uses_target_language,
    supported_script_counts,
    target_language_instruction,
)


def _chunk() -> dict:
    return {
        "id": "chunk-1",
        "document_id": "document-1",
        "content": "Digital infrastructure can be designed as a public good.",
        "title": "Evidence",
        "url": None,
    }


def _state(language: str = "en") -> dict:
    return {
        "query": "Can digital infrastructure be a public good?",
        "language": language,
        "route": "retrieve_docs",
        "retrieved_chunks": [_chunk()],
    }


class DominantScriptContractTests(unittest.TestCase):
    def test_explicit_target_instructions_cover_all_supported_languages(self):
        for language, name in (("en", "English"), ("hi", "Hindi"), ("bn", "Bengali")):
            with self.subTest(language=language):
                instruction = target_language_instruction(language)
                self.assertIn(f"Target output language: {name}", instruction)
                self.assertIn("even if the evidence", instruction)

    def test_english_accepts_latin_and_rejects_indic_dominance(self):
        self.assertTrue(answer_uses_target_language("A grounded English answer.", "en"))
        self.assertFalse(answer_uses_target_language("यह उत्तर हिंदी में है।", "en"))
        self.assertFalse(answer_uses_target_language("এই উত্তর বাংলায় লেখা।", "en"))

    def test_hindi_and_bengali_accept_their_dominant_scripts(self):
        self.assertTrue(answer_uses_target_language("यह सत्यापित हिंदी उत्तर है।", "hi"))
        self.assertTrue(answer_uses_target_language("এটি যাচাইকৃত বাংলা উত্তর।", "bn"))

    def test_mixed_english_allows_names_numbers_urls_and_acronyms(self):
        answer = "PM-KISAN serves 1.4 billion users via https://india.gov.in and Aadhaar आधार."
        self.assertTrue(answer_uses_target_language(answer, "en"))

    def test_urls_and_citation_identifiers_do_not_determine_language(self):
        text = (
            "https://india.gov.in "
            "[chunk_id=english-looking-id] "
            "548addec-36c6-4d9a-85e2-f3b406c5362d"
        )
        self.assertEqual(
            supported_script_counts(text),
            {"latin": 0, "devanagari": 0, "bengali": 0},
        )
        self.assertFalse(answer_uses_target_language(text, "en"))

    def test_empty_fails_and_unknown_language_is_safe(self):
        self.assertFalse(answer_uses_target_language("", "en"))
        self.assertTrue(answer_uses_target_language("", "unknown"))


class BoundedCorrectionTests(unittest.TestCase):
    def test_valid_correction_is_returned_and_citations_are_whitelisted(self):
        first = GeneratedAnswer(
            answer="यह उत्तर गलत भाषा में है।",
            confidence=0.9,
            citation_ids=["chunk-1"],
            abstained=False,
        )
        corrected = GeneratedAnswer(
            answer="Digital infrastructure can be designed as a public good.",
            confidence=0.9,
            citation_ids=["chunk-1", "fabricated", "chunk-1"],
            abstained=False,
        )
        with patch.object(
            graph, "generate_structured", side_effect=[first, corrected]
        ) as call:
            update = asyncio.run(graph.generate_node(_state()))

        self.assertEqual(call.call_count, 2)
        self.assertEqual(update["answer"], corrected.answer)
        self.assertEqual([item["chunk_id"] for item in update["citations"]], ["chunk-1"])
        self.assertIn(
            "Target output language: English",
            call.call_args_list[0].kwargs["system_prompt"],
        )
        self.assertIn(
            "Correction required", call.call_args_list[1].kwargs["system_prompt"]
        )
        self.assertEqual(
            call.call_args_list[0].kwargs["user_prompt"],
            call.call_args_list[1].kwargs["user_prompt"],
        )

    def test_invalid_second_output_returns_localized_abstention_without_leak(self):
        first_text = "पहला निजी गलत उत्तर।"
        second_text = "दूसरा निजी गलत उत्तर।"
        prompt_secret = "PROMPT_SECRET_do_not_log"
        evidence_secret = "EVIDENCE_SECRET_do_not_log"
        state = _state()
        state["query"] = prompt_secret
        state["retrieved_chunks"][0]["content"] = evidence_secret
        outputs = [
            GeneratedAnswer(
                answer=first_text,
                confidence=1,
                citation_ids=["chunk-1"],
                abstained=False,
            ),
            GeneratedAnswer(
                answer=second_text,
                confidence=1,
                citation_ids=["chunk-1"],
                abstained=False,
            ),
        ]
        with (
            self.assertLogs("app.agent.graph", level="WARNING") as captured,
            patch.object(graph, "generate_structured", side_effect=outputs) as call,
        ):
            update = asyncio.run(graph.generate_node(state))

        self.assertEqual(call.call_count, 2)
        self.assertEqual(update["answer"], abstention_message(prompt_secret, "en"))
        self.assertEqual(update["confidence"], 0.0)
        self.assertEqual(update["citations"], [])
        logs = "\n".join(captured.output)
        self.assertIn("target_language=en", logs)
        self.assertIn("detected_script=devanagari", logs)
        self.assertNotIn(first_text, logs)
        self.assertNotIn(second_text, logs)
        self.assertNotIn(prompt_secret, logs)
        self.assertNotIn(evidence_secret, logs)

    def test_route_and_retrieval_run_once_when_answer_is_corrected(self):
        route = RouteDecision(route="retrieve_docs", scheme_name_hint=None)
        first = GeneratedAnswer(
            answer="यह उत्तर हिंदी में है।",
            confidence=0.9,
            citation_ids=["chunk-1"],
            abstained=False,
        )
        corrected = GeneratedAnswer(
            answer="Digital infrastructure can be a public good.",
            confidence=0.9,
            citation_ids=["chunk-1"],
            abstained=False,
        )
        retrieve = AsyncMock(return_value=[_chunk()])
        session = object()
        with (
            patch.object(
                graph,
                "generate_structured",
                side_effect=[route, first, corrected],
            ) as generate,
            patch.object(graph, "retrieve_docs_tool", retrieve),
        ):
            result = asyncio.run(graph.run_agent(session, _state()["query"], language="en"))

        stages = [item.kwargs["stage"] for item in generate.call_args_list]
        self.assertEqual(stages.count("route_decision"), 1)
        self.assertEqual(stages.count("answer_generation"), 2)
        retrieve.assert_awaited_once_with(session, _state()["query"], "en")
        self.assertEqual(result["answer"], corrected.answer)


if __name__ == "__main__":
    unittest.main()
