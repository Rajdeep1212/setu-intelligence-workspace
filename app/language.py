"""Deterministic dominant-script checks for supported answer languages."""

from __future__ import annotations

import re
import unicodedata


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
}

LANGUAGE_SCRIPTS = {
    "en": "latin",
    "hi": "devanagari",
    "bn": "bengali",
}

MIN_DOMINANT_SHARE = 0.60

IGNORED_IDENTIFIER_PATTERN = re.compile(
    r"https?://\S+|www\.\S+|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|"
    r"\[(?:chunk_id|document_id)=[^\]]+\]",
    re.IGNORECASE,
)


def supported_script_counts(text: str) -> dict[str, int]:
    """Count letters from supported scripts; ignore numbers and punctuation."""
    counts = {"latin": 0, "devanagari": 0, "bengali": 0}
    text_without_identifiers = IGNORED_IDENTIFIER_PATTERN.sub(" ", text)
    for character in text_without_identifiers:
        if not unicodedata.category(character).startswith("L"):
            continue
        name = unicodedata.name(character, "")
        if "LATIN" in name:
            counts["latin"] += 1
        elif "DEVANAGARI" in name:
            counts["devanagari"] += 1
        elif "BENGALI" in name:
            counts["bengali"] += 1
    return counts


def dominant_supported_script(text: str) -> str:
    """Return the uniquely dominant supported script, or ``none``/``mixed``."""
    counts = supported_script_counts(text)
    highest = max(counts.values())
    if highest == 0:
        return "none"
    leaders = [script for script, count in counts.items() if count == highest]
    return leaders[0] if len(leaders) == 1 else "mixed"


def answer_uses_target_language(text: str, language: str | None) -> bool:
    """Validate that the target script has at least 60% of supported letters.

    The threshold permits ordinary foreign-script names and acronyms while
    rejecting empty answers and answers substantially written in another
    supported script. Unknown language values retain the prior permissive
    behavior instead of causing a request failure.
    """
    target_script = LANGUAGE_SCRIPTS.get(language or "")
    if target_script is None:
        return True
    if not text.strip():
        return False

    counts = supported_script_counts(text)
    supported_letters = sum(counts.values())
    if supported_letters == 0:
        return False

    target_count = counts[target_script]
    return (
        target_count > 0
        and dominant_supported_script(text) == target_script
        and target_count / supported_letters >= MIN_DOMINANT_SHARE
    )


def target_language_instruction(language: str, *, correction: bool = False) -> str:
    """Build an explicit, content-free output-language instruction."""
    name = LANGUAGE_NAMES.get(language)
    script = LANGUAGE_SCRIPTS.get(language)
    if name is None or script is None:
        return ""

    instruction = (
        f"Target output language: {name}. Write the complete answer in {name} "
        f"using predominantly {script.title()} script, even if the evidence "
        "uses another language. Do not translate the answer into another language."
    )
    if correction:
        instruction += (
            " Correction required: generate the grounded answer again from the "
            "same evidence and follow the target language exactly."
        )
    return instruction
