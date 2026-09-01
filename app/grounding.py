"""Deterministic citation validation and grounded-abstention helpers."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


ABSTENTION_MESSAGES = {
    "en": "I couldn't find enough relevant evidence to answer that.",
    "hi": "उत्तर देने के लिए मुझे पर्याप्त प्रासंगिक साक्ष्य नहीं मिला।",
    "bn": "উত্তর দেওয়ার জন্য পর্যাপ্ত প্রাসঙ্গিক প্রমাণ পাইনি।",
}


def query_language(query: str, requested_language: str | None) -> str:
    """Use an explicit language, otherwise infer only the scripts we support."""
    if requested_language in ABSTENTION_MESSAGES:
        return requested_language
    if re.search(r"[\u0980-\u09ff]", query):
        return "bn"
    if re.search(r"[\u0900-\u097f]", query):
        return "hi"
    return "en"


def abstention_message(query: str, language: str | None = None) -> str:
    return ABSTENTION_MESSAGES[query_language(query, language)]


def _normalized_evidence(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def select_citations(
    retrieved_chunks: Iterable[dict], requested_ids: Iterable[str]
) -> list[dict]:
    """Validate model-selected IDs and return citations in retrieval order."""
    requested = {str(chunk_id) for chunk_id in requested_ids}
    seen_ids: set[str] = set()
    seen_evidence: set[str] = set()
    citations: list[dict] = []

    for chunk in retrieved_chunks:
        chunk_id = str(chunk["id"])
        if chunk_id not in requested or chunk_id in seen_ids:
            continue

        evidence_key = _normalized_evidence(str(chunk.get("content", "")))
        if evidence_key in seen_evidence:
            continue

        seen_ids.add(chunk_id)
        seen_evidence.add(evidence_key)
        citations.append(
            {
                "chunk_id": chunk_id,
                "document_id": str(chunk["document_id"]),
                "title": chunk.get("title"),
                "source": chunk.get("source"),
                "url": chunk.get("url"),
                "snippet": str(chunk.get("content", ""))[:200],
            }
        )

    return citations
