import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.agent.graph import generate_node, run_agent
from app.agent.models import GeneratedAnswer, GeneratedClaim
from app.grounding import abstention_message, select_citations
from app.schemas import AnswerSection, Citation, QueryResponse
from eval.grounding_metrics import extract_claims, structural_replay, summarize


def chunk(chunk_id, content, title=None):
    return {
        "id": chunk_id,
        "document_id": f"document-{chunk_id}",
        "content": content,
        "title": title,
        "url": f"https://example.test/{chunk_id}",
    }


class CitationSelectionTests(unittest.TestCase):
    def test_personal_eligibility_fails_closed_without_provider_or_database(self):
        session = object()
        with (
            patch("app.agent.graph.generate_structured") as generate,
            patch("app.agent.graph.retrieve_docs_tool") as retrieve,
        ):
            update = asyncio.run(
                run_agent(
                    session,
                    "Could I qualify for this scheme?",
                    language="en",
                )
            )

        generate.assert_not_called()
        retrieve.assert_not_called()
        self.assertEqual(update["route"], "check_eligibility")
        self.assertEqual(update["response_status"], "eligibility_unverified")
        self.assertEqual(update["citations"], [])
        self.assertIsNone(update["confidence"])

    def test_ids_are_whitelisted_deduplicated_and_retrieval_ordered(self):
        chunks = [chunk("first", "Evidence one"), chunk("second", "Evidence two")]
        citations = select_citations(
            chunks, ["second", "fabricated", "first", "second"]
        )
        self.assertEqual([item["chunk_id"] for item in citations], ["first", "second"])

    def test_exact_normalized_duplicate_evidence_is_removed(self):
        chunks = [
            chunk("first", " একই   প্রমাণ ", "বাংলা নথি"),
            chunk("second", "একই প্রমাণ", "অন্য নথি"),
        ]
        citations = select_citations(chunks, ["first", "second"])
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["title"], "বাংলা নথি")

    def test_unicode_metadata_and_chunk_identifier_are_preserved(self):
        citations = select_citations(
            [chunk("বাংলা-চাঙ্ক", "প্রমাণ", "সরকারি বাংলা নথি")],
            ["বাংলা-চাঙ্ক"],
        )
        self.assertEqual(citations[0]["chunk_id"], "বাংলা-চাঙ্ক")
        self.assertEqual(citations[0]["snippet"], "প্রমাণ")

    def test_retrieval_answer_uses_only_valid_selected_evidence(self):
        state = {
            "query": "What is supported?",
            "language": "en",
            "route": "retrieve_docs",
            "retrieved_chunks": [
                chunk("one", "Supporting text"),
                chunk("two", "Merely related text"),
            ],
        }
        result = GeneratedAnswer(
            answer="Supported answer.",
            confidence=0.8,
            citation_ids=["one"],
            abstained=False,
        )
        with patch(
            "app.agent.graph.generate_structured", return_value=result
        ) as generate:
            update = asyncio.run(generate_node(state))

        self.assertEqual(update["answer"], "Supported answer.")
        self.assertEqual([c["chunk_id"] for c in update["citations"]], ["one"])
        self.assertEqual(
            update["sections"],
            [{"text": "Supported answer.", "citation_ids": ["one"]}],
        )
        prompt = generate.call_args.kwargs["user_prompt"]
        self.assertIn("[chunk_id=one]", prompt)
        self.assertIn("[chunk_id=two]", prompt)

    def test_no_valid_selected_evidence_forces_localized_abstention(self):
        state = {
            "query": "यह क्या है?",
            "language": "hi",
            "route": "retrieve_docs",
            "retrieved_chunks": [chunk("one", "कुछ प्रमाण")],
        }
        result = GeneratedAnswer(
            answer="An unsupported answer.",
            confidence=0.9,
            citation_ids=["fabricated"],
            abstained=False,
        )
        with patch("app.agent.graph.generate_structured", return_value=result):
            update = asyncio.run(generate_node(state))

        self.assertEqual(update["answer"], abstention_message(state["query"], "hi"))
        self.assertEqual(update["citations"], [])
        self.assertEqual(update["confidence"], 0.0)
        self.assertEqual(update["response_status"], "abstained")

    def test_claim_specific_citations_are_validated_and_unlinked_claim_stays_unbadged(self):
        state = {
            "query": "What is supported?",
            "language": "en",
            "route": "retrieve_docs",
            "retrieved_chunks": [chunk("one", "Supporting text")],
        }
        result = GeneratedAnswer(
            answer="Legacy answer is not authoritative when claims are present.",
            confidence=0.7,
            citation_ids=["one"],
            claims=[
                GeneratedClaim(text="Supported section.", citation_ids=["one"]),
                GeneratedClaim(text="Unlinked section.", citation_ids=[]),
            ],
            abstained=False,
        )
        with patch("app.agent.graph.generate_structured", return_value=result):
            update = asyncio.run(generate_node(state))

        self.assertEqual(update["answer"], "Supported section. Unlinked section.")
        self.assertEqual(
            update["sections"],
            [
                {"text": "Supported section.", "citation_ids": ["one"]},
                {"text": "Unlinked section.", "citation_ids": []},
            ],
        )

    def test_unknown_claim_citation_fails_closed(self):
        state = {
            "query": "What is supported?",
            "language": "en",
            "route": "retrieve_docs",
            "retrieved_chunks": [chunk("one", "Supporting text")],
        }
        result = GeneratedAnswer(
            answer="Unsupported.",
            confidence=0.9,
            citation_ids=["one"],
            claims=[GeneratedClaim(text="Unsupported.", citation_ids=["fabricated"])],
            abstained=False,
        )
        with patch("app.agent.graph.generate_structured", return_value=result):
            update = asyncio.run(generate_node(state))

        self.assertEqual(update["response_status"], "abstained")
        self.assertEqual(update["citations"], [])
        self.assertEqual(update["sections"], [])

    def test_duplicate_claim_citation_ids_are_rejected(self):
        with self.assertRaises(ValidationError):
            GeneratedClaim(text="Claim", citation_ids=["one", "one"])

    def test_malformed_provider_claim_is_rejected(self):
        with self.assertRaises(ValidationError):
            GeneratedAnswer.model_validate(
                {
                    "answer": "Malformed claim.",
                    "confidence": 0.5,
                    "citation_ids": ["one"],
                    "claims": [{"text": " ", "citation_ids": [""]}],
                    "abstained": False,
                }
            )

    def test_api_contract_rejects_unknown_section_citation(self):
        with self.assertRaises(ValidationError):
            QueryResponse(
                answer="Claim.",
                citations=[Citation(chunk_id="one", document_id="document-one")],
                sections=[AnswerSection(text="Claim.", citation_ids=["unknown"])],
            )

    def test_api_contract_rejects_duplicate_top_level_citations(self):
        with self.assertRaises(ValidationError):
            QueryResponse(
                answer="Claim.",
                citations=[
                    Citation(chunk_id="one", document_id="document-one"),
                    Citation(chunk_id="one", document_id="document-two"),
                ],
            )

    def test_empty_retrieval_abstains_without_calling_provider(self):
        state = {
            "query": "কী তথ্য আছে?",
            "language": None,
            "route": "retrieve_docs",
            "retrieved_chunks": [],
        }
        with patch("app.agent.graph.generate_structured") as generate:
            update = asyncio.run(generate_node(state))

        generate.assert_not_called()
        self.assertEqual(update["answer"], abstention_message(state["query"], None))
        self.assertEqual(update["citations"], [])

    def test_structured_output_rejects_more_than_retrieval_limit(self):
        with self.assertRaises(ValidationError):
            GeneratedAnswer(
                answer="Too many citations",
                confidence=0.5,
                citation_ids=[str(index) for index in range(6)],
                abstained=False,
            )

    def test_structured_output_requires_citation_contract_fields(self):
        with self.assertRaises(ValidationError):
            GeneratedAnswer(answer="Incomplete output", confidence=0.5)


class GroundingEvaluationTests(unittest.TestCase):
    def test_claim_splitter_handles_all_supported_sentence_terminators(self):
        answer = "English fact. हिंदी तथ्य। বাংলা তথ্য।"
        self.assertEqual(len(extract_claims(answer)), 3)

    def test_structural_replay_improves_controlled_precision(self):
        dataset_path = Path(__file__).parents[1] / "eval" / "grounding_set.jsonl"
        with dataset_path.open(encoding="utf-8") as handle:
            dataset = [json.loads(line) for line in handle if line.strip()]
        before, after = structural_replay(dataset)
        before_score = summarize(dataset, before)
        after_score = summarize(dataset, after)

        self.assertEqual(before_score["queries"], 15)
        self.assertEqual(before_score["answerable"], 12)
        self.assertEqual(before_score["unanswerable"], 3)
        self.assertGreater(
            after_score["overall"]["citation_precision"],
            before_score["overall"]["citation_precision"],
        )
        self.assertEqual(after_score["overall"]["support_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()
