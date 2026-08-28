import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.agent.graph import generate_node
from app.agent.models import GeneratedAnswer
from app.grounding import abstention_message, select_citations
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
            citation_ids=["one", "invented"],
            abstained=False,
        )
        with patch(
            "app.agent.graph.generate_structured", return_value=result
        ) as generate:
            update = asyncio.run(generate_node(state))

        self.assertEqual(update["answer"], "Supported answer.")
        self.assertEqual([c["chunk_id"] for c in update["citations"]], ["one"])
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
