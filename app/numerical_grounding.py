"""Deterministic validation of factual numeric expressions against evidence."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class NumericalGroundingResult:
    """Content-free validation metadata safe to use for observability."""

    expression_count: int
    unsupported_count: int

    @property
    def is_valid(self) -> bool:
        return self.unsupported_count == 0


@dataclass(frozen=True)
class _NumericFact:
    number: str
    scale: str | None
    is_percent: bool
    is_ordinal: bool
    currency: str | None
    unit: str | None


_SCALE_ALIASES = {
    "thousand": "thousand",
    "thousands": "thousand",
    "हजार": "thousand",
    "हज़ार": "thousand",
    "হাজার": "thousand",
    "million": "million",
    "millions": "million",
    "मिलियन": "million",
    "মিলিয়ন": "million",
    "billion": "billion",
    "billions": "billion",
    "बिलियन": "billion",
    "বিলিয়ন": "billion",
    "lakh": "lakh",
    "lakhs": "lakh",
    "lac": "lakh",
    "lacs": "lakh",
    "लाख": "lakh",
    "লাখ": "lakh",
    "crore": "crore",
    "crores": "crore",
    "करोड": "crore",
    "करोड़": "crore",
    "কোটি": "crore",
}

_PERCENT_ALIASES = {"%", "percent", "percentage", "प्रतिशत", "শতাংশ"}

_CURRENCY_ALIASES = {
    "₹": "inr",
    "inr": "inr",
    "rs": "inr",
    "$": "usd",
    "usd": "usd",
}

# Deliberately small, reviewable coverage for the word-form gap found during
# the controlled R3-D query. This is lexical normalization, not general
# natural-language number understanding.
_NUMBER_WORD_ALIASES: dict[str, tuple[str, bool]] = {
    "one": ("1", False),
    "two": ("2", False),
    "three": ("3", False),
    "first": ("1", True),
    "second": ("2", True),
    "third": ("3", True),
    "एक": ("1", False),
    "दो": ("2", False),
    "तीन": ("3", False),
    "पहला": ("1", True),
    "पहली": ("1", True),
    "दूसरा": ("2", True),
    "दूसरी": ("2", True),
    "तीसरा": ("3", True),
    "तीसरी": ("3", True),
    "এক": ("1", False),
    "দুই": ("2", False),
    "তিন": ("3", False),
    "প্রথম": ("1", True),
    "দ্বিতীয়": ("2", True),
    "দ্বিতীয়": ("2", True),
    "তৃতীয়": ("3", True),
    "তৃতীয়": ("3", True),
}

_UNIT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "between", "by", "for",
    "from", "has", "have", "in", "is", "of", "on", "or", "over",
    "than", "that", "the", "through", "to", "under", "was", "were",
    "which", "who", "with", "within", "अधिक", "और", "का", "की", "के",
    "तक", "में", "से", "এর", "জন্য", "থেকে", "পর্যন্ত", "সালে",
    "সালের",
}

_IDENTIFIER_PATTERN = re.compile(
    r"https?://\S+|www\.\S+|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|"
    r"\[(?:chunk_id|document_id|citation_id)=[^\]]+\]|"
    r"\b(?:chunk|document|citation)[_-]?id\s*[:=]\s*\S+|"
    r"\b(?:chunk|document|citation)-[A-Za-z0-9_-]+\b",
    re.IGNORECASE,
)
_ORDINAL_WORD_PATTERN = "|".join(
    sorted(
        (
            re.escape(value)
            for value, (_, is_ordinal) in _NUMBER_WORD_ALIASES.items()
            if is_ordinal
        ),
        key=len,
        reverse=True,
    )
)
_STRUCTURAL_NUMBER_PATTERN = re.compile(
    rf"(?m)^[ \t]*\(?\d{{1,3}}\)?[.)](?=\s)"
    rf"(?:\s*(?:{_ORDINAL_WORD_PATTERN})(?![\w]))?",
    re.IGNORECASE,
)
_SCALE_PATTERN = "|".join(
    sorted((re.escape(value) for value in _SCALE_ALIASES), key=len, reverse=True)
)
_PERCENT_PATTERN = "|".join(
    sorted((re.escape(value) for value in _PERCENT_ALIASES), key=len, reverse=True)
)
_CURRENCY_PATTERN = "|".join(
    sorted((re.escape(value) for value in _CURRENCY_ALIASES), key=len, reverse=True)
)
_NUMBER_WORD_PATTERN = "|".join(
    sorted((re.escape(value) for value in _NUMBER_WORD_ALIASES), key=len, reverse=True)
)
_NUMBER_PATTERN = re.compile(
    rf"(?<![\w])(?:(?P<currency>{_CURRENCY_PATTERN})\s*)?"
    rf"(?P<number>\d+(?:,\d{{2,3}})*(?:\.\d+)?)"
    rf"(?P<ordinal>st|nd|rd|th)?"
    rf"(?:\s*(?P<scale>{_SCALE_PATTERN}))?"
    rf"(?:\s*(?P<percent>{_PERCENT_PATTERN}))?(?![\w])",
    re.IGNORECASE,
)
_WORD_NUMBER_PATTERN = re.compile(
    rf"(?<![\w])(?P<word>{_NUMBER_WORD_PATTERN})(?![\w])", re.IGNORECASE
)
_WORD_SUFFIX_PATTERN = re.compile(
    rf"^\s*(?:(?P<scale>{_SCALE_PATTERN}))?"
    rf"(?:\s*(?P<percent>{_PERCENT_PATTERN}))?",
    re.IGNORECASE,
)
_FOLLOWING_WORD_PATTERN = re.compile(r"^\s*(?P<unit>[^\W\d_]+)", re.UNICODE)


def _ascii_digits(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    converted: list[str] = []
    for character in normalized:
        if unicodedata.category(character) == "Nd":
            try:
                converted.append(str(unicodedata.digit(character)))
                continue
            except (TypeError, ValueError):
                pass
        converted.append(character)
    return "".join(converted)


def _content_for_scanning(value: str) -> str:
    content = _ascii_digits(value).casefold()
    content = _IDENTIFIER_PATTERN.sub(" ", content)
    return _STRUCTURAL_NUMBER_PATTERN.sub(" ", content)


def _canonical_number(value: str) -> str:
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation:
        return value.replace(",", "")
    canonical = format(number.normalize(), "f")
    return canonical.rstrip("0").rstrip(".") if "." in canonical else canonical


def _canonical_unit(value: str | None) -> str | None:
    if not value:
        return None
    unit = unicodedata.normalize("NFKC", value).casefold()
    if unit in _UNIT_STOPWORDS:
        return None
    if unit == "people":
        return "person"
    if unit.endswith("ies") and len(unit) > 3:
        return f"{unit[:-3]}y"
    if unit.endswith("s") and len(unit) > 3:
        return unit[:-1]
    return unit


def _extract_numeric_facts(value: str) -> list[_NumericFact]:
    content = _content_for_scanning(value)
    facts: list[_NumericFact] = []
    for match in _NUMBER_PATTERN.finditer(content):
        scale_value = match.group("scale")
        percent_value = match.group("percent")
        scale = _SCALE_ALIASES.get(scale_value.casefold()) if scale_value else None
        is_percent = bool(percent_value)
        following = _FOLLOWING_WORD_PATTERN.match(content[match.end() :])
        unit = None if is_percent else _canonical_unit(
            following.group("unit") if following else None
        )
        facts.append(
            _NumericFact(
                number=_canonical_number(match.group("number")),
                scale=scale,
                is_percent=is_percent,
                is_ordinal=bool(match.group("ordinal")),
                currency=(
                    _CURRENCY_ALIASES[match.group("currency").casefold()]
                    if match.group("currency")
                    else None
                ),
                unit=unit,
            )
        )
    for match in _WORD_NUMBER_PATTERN.finditer(content):
        number, is_ordinal = _NUMBER_WORD_ALIASES[match.group("word").casefold()]
        suffix = _WORD_SUFFIX_PATTERN.match(content[match.end() :])
        scale_value = suffix.group("scale") if suffix else None
        percent_value = suffix.group("percent") if suffix else None
        scale = _SCALE_ALIASES.get(scale_value.casefold()) if scale_value else None
        is_percent = bool(percent_value)
        suffix_end = match.end() + (suffix.end() if suffix else 0)
        following = _FOLLOWING_WORD_PATTERN.match(content[suffix_end:])
        unit = None if is_percent else _canonical_unit(
            following.group("unit") if following else None
        )
        facts.append(
            _NumericFact(
                number=number,
                scale=scale,
                is_percent=is_percent,
                is_ordinal=is_ordinal,
                currency=None,
                unit=unit,
            )
        )
    return facts


def _is_supported(claim: _NumericFact, evidence: set[_NumericFact]) -> bool:
    for candidate in evidence:
        if (
            claim.number != candidate.number
            or claim.scale != candidate.scale
            or claim.is_percent != candidate.is_percent
            or claim.is_ordinal != candidate.is_ordinal
            or claim.currency != candidate.currency
        ):
            continue
        if claim.unit is None or claim.unit == candidate.unit:
            return True
    return False


def validate_numerical_grounding(
    answer: str, cited_evidence: Iterable[str]
) -> NumericalGroundingResult:
    """Check every answer number against full valid cited evidence."""
    answer_facts = _extract_numeric_facts(answer)
    evidence_facts = {
        fact for content in cited_evidence for fact in _extract_numeric_facts(content)
    }
    unsupported_count = sum(
        not _is_supported(claim, evidence_facts) for claim in answer_facts
    )
    return NumericalGroundingResult(
        expression_count=len(answer_facts),
        unsupported_count=unsupported_count,
    )
