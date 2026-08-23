"""
Language-aware chunking — Week 1.

English uses '.', '!', '?' as sentence terminators. Hindi and Bengali both
use the danda '।' (U+0964) as their primary sentence terminator, borrowed
from Sanskrit convention — splitting on '.' alone will silently merge
sentences (or split mid-abbreviation) for those two languages.

This is a lightweight regex-based splitter with no extra dependencies. If
retrieval quality on Hindi/Bengali eval questions is noticeably worse than
English in Week 2, swap this for `indic-nlp-library`'s sentence tokenizer,
which handles more edge cases (abbreviations, embedded numerals, etc).
"""

from __future__ import annotations

import re

_SENTENCE_BOUNDARY = {
    "en": re.compile(r"(?<=[.!?])\s+"),
    "hi": re.compile(r"(?<=[।!?])\s+"),
    "bn": re.compile(r"(?<=[।!?])\s+"),
}


def split_sentences(text: str, language: str) -> list[str]:
    pattern = _SENTENCE_BOUNDARY.get(language, _SENTENCE_BOUNDARY["en"])
    sentences = [s.strip() for s in pattern.split(text.strip()) if s.strip()]
    return sentences


def chunk_text(
    text: str,
    language: str,
    chunk_size: int = 500,
    overlap_sentences: int = 1,
) -> list[str]:
    """
    Group sentences into chunks of roughly `chunk_size` characters, with the
    last `overlap_sentences` of each chunk repeated at the start of the
    next chunk so retrieval doesn't lose context at chunk boundaries.

    Character-based sizing (not token-based) is deliberate here: Hindi and
    Bengali tokenize very differently from English under most tokenizers,
    so a fixed token budget would produce wildly different chunk lengths
    per language. Character length is a simpler, more consistent proxy.
    """
    sentences = split_sentences(text, language)
    if not sentences:
        return []

    chunks: list[str] = []
    current_sentences: list[str] = []

    for sentence in sentences:
        candidate = " ".join(current_sentences + [sentence]).strip() if current_sentences else sentence
        if len(candidate) <= chunk_size:
            current_sentences.append(sentence)
            continue

        if current_sentences:
            chunks.append(" ".join(current_sentences).strip())
            # carry the tail sentences forward for continuity
            if overlap_sentences > 0:
                current_sentences = current_sentences[-overlap_sentences:]
                current_sentences.append(sentence)
            else:
                current_sentences = [sentence]
        else:
            # a single sentence longer than chunk_size — keep it whole
            chunks.append(sentence)
            current_sentences = []

    if current_sentences:
        chunks.append(" ".join(current_sentences).strip())

    return chunks
