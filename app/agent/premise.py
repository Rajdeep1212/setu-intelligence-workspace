"""Deterministic premise checks for traffic-fine questions (Phase 3).

A person at a checkpoint often asks a question that carries a claim, such as
"Police say the helmet fine is Rs 5,000. Is that right?". Language models
tend to accept such premises (docs/FINDINGS.md, C12). This module never calls
a model. It reads the question in English, Hindi or Bengali, finds the
offence, the place, whether it is a first or repeat offence and any claimed
amount, and compares the claim with the VERIFIED state compounding amounts in
data/traffic_offences.

Rules that keep it safe:
- It only triggers on questions that name an offence and use a fine word
  ("fine", "challan", "police", जुर्माना, জরিমানা ...), so ordinary questions
  about, say, linking a mobile phone to Aadhaar are left alone.
- A missing place yields a clarifying question, never a guess.
- Red-light jumping is under legal review and earphones are not named in the
  Act (C2), so neither is ever confirmed or contradicted.
- UNVERIFIED rows (all of Delhi today) neither confirm nor contradict.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "traffic_offences"
SUPPORTED_JURISDICTIONS = {"IN-WB": "West Bengal", "IN-KA": "Karnataka", "IN-DL": "Delhi"}
LEGAL_REVIEW_OFFENCES = {"red_light"}

# Order matters: earphones are checked before phones ("earphone" contains "phone").
_OFFENCE_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("earphones", ("earphone", "ear phone", "headphone", "earbud", "ईयरफ़ोन", "ईयरफोन", "हेडफ़ोन", "हेडफोन", "ইয়ারফোন", "হেডফোন")),
    ("red_light", ("red light", "red-light", "signal jump", "jumping signal", "jumped the signal", "jump the signal", "jumping the signal", "traffic signal", "लाल बत्ती", "रेड लाइट", "सिग्नल", "লাল বাতি", "রেড লাইট", "সিগন্যাল")),
    ("triple_riding", ("triple riding", "triple ride", "triple-riding", "three people", "three persons", "three riders", "three on a", "more than one pillion", "तीन लोग", "तीन सवारी", "ट्रिपल", "তিনজন", "তিন জন", "ট্রিপল")),
    ("helmet", ("helmet", "headgear", "हेलमेट", "হেলমেট")),
    ("phone_device", ("mobile", "phone", "handheld", "hand-held", "मोबाइल", "फ़ोन", "फोन", "মোবাইল", "ফোন")),
    ("no_licence", ("licence", "license", "लाइसेंस", "লাইসেন্স")),
    ("no_insurance", ("insurance", "insured", "बीमा", "বিমা", "বীমা", "ইনস্যুরেন্স")),
    ("overspeeding", ("overspeed", "over-speed", "over speed", "speeding", "speed limit", "ओवरस्पीड", "तेज रफ्तार", "तेज़ रफ़्तार", "ওভারস্পিড", "দ্রুত গতি", "অতিরিক্ত গতি")),
)
# Fine words and enforcement context. "pay" is deliberately absent: it would
# catch "pay my insurance premium" or "pay the licence fee".
_FINE_TERMS = (
    "fine", "penalty", "challan", "compound", "police", "policeman", "cop", "how much",
    "officer", "constable", "sergeant", "caught", "stopped me",
    "जुर्माना", "चालान", "पुलिस", "कितना", "जुर्माने", "पकड़", "लगेंगे", "लगेगा", "हवलदार",
    "জরিমানা", "চালান", "পুলিশ", "কত", "ধরা", "ধরল", "সার্জেন্ট",
)
_PLACE_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("IN-WB", ("kolkata", "calcutta", "howrah", "west bengal", "कोलकाता", "कलकत्ता", "पश्चिम बंगाल", "কলকাতা", "পশ্চিমবঙ্গ", "হাওড়া")),
    ("IN-KA", ("bengaluru", "bangalore", "karnataka", "mysuru", "mysore", "बेंगलुरु", "बंगलौर", "बैंगलोर", "कर्नाटक", "বেঙ্গালুরু", "ব্যাঙ্গালোর", "কর্ণাটক")),
    ("IN-DL", ("new delhi", "delhi", "दिल्ली", "দিল্লি")),
)
# Places SETU has no verified table for; naming one must not trigger "which state?".
_UNSUPPORTED_PLACES = (
    "mumbai", "maharashtra", "pune", "chennai", "tamil nadu", "hyderabad", "telangana", "gujarat",
    "ahmedabad", "uttar pradesh", "lucknow", "noida", "rajasthan", "jaipur", "kerala", "bihar", "patna",
    "odisha", "assam", "punjab", "haryana", "gurugram", "gurgaon", "goa", "andhra", "madhya pradesh",
    "मुंबई", "महाराष्ट्र", "चेन्नई", "हैदराबाद", "लखनऊ", "जयपुर", "पटना", "মুম্বাই", "চেন্নাই", "হায়দরাবাদ",
)
_FIRST_TERMS = ("first", "1st", "पहली बार", "पहली", "प्रथम", "প্রথমবার", "প্রথম বার", "প্রথম")
_REPEAT_TERMS = ("second", "repeat", "again", "subsequent", "next time", "दूसरी बार", "दोबारा", "फिर से", "দ্বিতীয়বার", "দ্বিতীয় বার", "আবার", "পুনরায়")

_DIGIT_TABLE = str.maketrans("०१२३४५६७८९০১২৩৪৫৬৭৮৯", "01234567890123456789")
_UNIT_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "twenty": 20, "twenty-five": 25, "twenty five": 25, "fifty": 50,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9,
    "दस": 10, "बीस": 20, "पच्चीस": 25, "पचास": 50,
    "এক": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6, "সাত": 7, "আট": 8, "নয়": 9,
    "দশ": 10, "বিশ": 20, "পঁচিশ": 25, "পঞ্চাশ": 50,
}
_MULTIPLIERS = {
    "hundred": 100, "thousand": 1000, "k": 1000, "lakh": 100000, "lakhs": 100000, "lac": 100000,
    "सौ": 100, "हज़ार": 1000, "हजार": 1000, "लाख": 100000,
    "শো": 100, "হাজার": 1000, "লাখ": 100000,
}
_CURRENCY_BEFORE = r"(?:₹|rs\.?|inr|रु\.?|रुपये|रुपए|টাকা)"
_CURRENCY_AFTER = r"(?:rupees?|rs\.?|inr|रुपये|रुपए|रुपया|টাকা|টাকার)"
_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_MULT = "|".join(sorted((re.escape(word) for word in _MULTIPLIERS), key=len, reverse=True))
_WORDS = "|".join(sorted((re.escape(word) for word in _UNIT_WORDS), key=len, reverse=True))
_AMOUNT_PATTERNS = (
    # ₹5,000 / Rs 10k / ₹ 2 lakh
    re.compile(rf"{_CURRENCY_BEFORE}\s*(?P<num>{_NUMBER})\s*(?P<mult>{_MULT})?(?![\w])", re.IGNORECASE),
    # 5000 rupees / 10 thousand rupees / 25 हज़ार / ১০ হাজার
    re.compile(rf"(?<![\w₹])(?P<num>{_NUMBER})\s*(?P<mult>{_MULT})\s*{_CURRENCY_AFTER}?", re.IGNORECASE),
    re.compile(rf"(?<![\w₹])(?P<num>{_NUMBER})\s*{_CURRENCY_AFTER}", re.IGNORECASE),
    # five thousand rupees / पांच हज़ार / দশ হাজার টাকা
    re.compile(rf"(?<![\w])(?P<word>{_WORDS})\s+(?P<mult>{_MULT})(?![\w])", re.IGNORECASE),
)
# A bare number right after a fine word ("challan 3000 hai kya?"). The gap may
# hold a few short words but no date words, so "fine in 2019" is never a claim.
_FINE_WORD_PATTERN = "|".join(
    sorted((re.escape(term) for term in ("fine", "challan", "penalty", "जुर्माना", "चालान", "জরিমানা", "চালান")), key=len, reverse=True)
)
_BARE_AFTER_FINE = re.compile(rf"(?:{_FINE_WORD_PATTERN})(?P<gap>[^\d₹]{{0,24}}?)(?P<num>\d[\d,]*)(?![\d,]*\s*(?:{_MULT}))", re.IGNORECASE)
_DATE_GAP = re.compile(r"(?<![a-z])(?:in|since|from|year|till|until|before|after|on|dated)(?![a-z])|में|साल|সালে|সাল", re.IGNORECASE)


@dataclass(frozen=True)
class QueryFacts:
    offences: tuple[str, ...]
    jurisdiction: str | None
    place_supported: bool
    occurrence: str | None
    claimed_inr: tuple[int, ...]
    is_fine_question: bool
    year: int | None = None

    @property
    def offence_id(self) -> str | None:
        return self.offences[0] if len(self.offences) == 1 else None


@dataclass
class PremiseResult:
    verdict: str
    offence_id: str | None = None
    jurisdiction: str | None = None
    occurrence: str | None = None
    claimed_inr: int | None = None
    verified_amounts: list[dict[str, Any]] = field(default_factory=list)
    source: dict[str, str] | None = None
    schedule_row: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "offence_id": self.offence_id,
            "jurisdiction": self.jurisdiction,
            "occurrence": self.occurrence,
            "claimed_inr": self.claimed_inr,
            "verified_amounts": self.verified_amounts,
            "source": self.source,
            "schedule_row": self.schedule_row,
        }


def _normalize(text: str) -> str:
    return " ".join(text.translate(_DIGIT_TABLE).casefold().split())


def _contains(text: str, term: str) -> bool:
    # Latin terms match on word boundaries; Indic terms match as substrings
    # because inflections attach directly (लोगों, জরিমানা).
    if term.isascii():
        return re.search(rf"(?<![a-z]){re.escape(term)}", text) is not None
    return term in text


def find_offences(text: str) -> tuple[str, ...]:
    normalized = _normalize(text)
    found: list[str] = []
    for offence_id, terms in _OFFENCE_TERMS:
        if any(_contains(normalized, term) for term in terms):
            found.append(offence_id)
    if "earphones" in found and "phone_device" in found:
        found.remove("phone_device")
    return tuple(found)


def find_jurisdiction(text: str) -> tuple[str | None, bool]:
    """Return (jurisdiction, supported). (None, False) means an unsupported place was named."""
    normalized = _normalize(text)
    for code, terms in _PLACE_TERMS:
        if any(_contains(normalized, term) for term in terms):
            return code, True
    if any(_contains(normalized, term) for term in _UNSUPPORTED_PLACES):
        return None, False
    return None, True


def find_occurrence(text: str) -> str | None:
    normalized = _normalize(text)
    if any(_contains(normalized, term) for term in _REPEAT_TERMS):
        return "subsequent"
    if any(_contains(normalized, term) for term in _FIRST_TERMS):
        return "first"
    return None


def find_claimed_amounts(text: str) -> tuple[int, ...]:
    """Rupee amounts tied to a currency marker or a multiplier; bare numbers (years, counts) are ignored."""
    normalized = _normalize(text)
    amounts: list[tuple[int, int]] = []
    taken: list[range] = []
    for pattern in _AMOUNT_PATTERNS:
        for match in pattern.finditer(normalized):
            span = range(match.start(), match.end())
            if any(span.start < other.stop and other.start < span.stop for other in taken):
                continue
            if match.groupdict().get("word"):
                base = float(_UNIT_WORDS[match.group("word")])
            else:
                base = float(match.group("num").replace(",", ""))
            multiplier = _MULTIPLIERS.get(match.groupdict().get("mult") or "", 1)
            value = int(round(base * multiplier))
            if value > 0:
                taken.append(span)
                amounts.append((match.start(), value))
    if not amounts:
        for match in _BARE_AFTER_FINE.finditer(normalized):
            if _DATE_GAP.search(match.group("gap")):
                continue
            value = int(match.group("num").replace(",", ""))
            if value >= 100:
                amounts.append((match.start("num"), value))
    return tuple(value for _, value in sorted(amounts))


_YEAR = re.compile(r"(?<![\d₹,])(19[5-9]\d|20\d\d)(?![\d,])")


def find_year(text: str) -> int | None:
    """A calendar year named in the question (for example "in 2019"), if any."""
    normalized = _normalize(text)
    claimed = set(find_claimed_amounts(text))
    for match in _YEAR.finditer(normalized):
        value = int(match.group(1))
        if value not in claimed:
            return value
    return None


def extract_facts(query: str) -> QueryFacts:
    normalized = _normalize(query)
    offences = find_offences(query)
    jurisdiction, supported = find_jurisdiction(query)
    has_fine_word = any(_contains(normalized, term) for term in _FINE_TERMS)
    return QueryFacts(
        offences=offences,
        jurisdiction=jurisdiction,
        place_supported=supported,
        occurrence=find_occurrence(query),
        claimed_inr=find_claimed_amounts(query),
        is_fine_question=bool(offences) and has_fine_word,
        year=find_year(query),
    )


def missing_facts(query: str) -> list[str]:
    """Facts SETU must ask for before answering a traffic-fine question."""
    facts = extract_facts(query)
    if not facts.is_fine_question:
        return []
    missing: list[str] = []
    if facts.jurisdiction is None and facts.place_supported:
        missing.append("jurisdiction")
    if len(facts.offences) > 1:
        missing.append("offence")
    return missing


@lru_cache(maxsize=8)
def load_table(jurisdiction: str) -> dict[str, Any]:
    if jurisdiction not in SUPPORTED_JURISDICTIONS:
        raise KeyError(jurisdiction)
    path = DATA_DIR / f"{jurisdiction.removeprefix('IN-')}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _in_force(state: dict[str, Any], as_of: date | None, year: int | None) -> bool:
    """Whether the state amount applied on the date (or during the year) asked about."""
    start = date.fromisoformat(state["effective_from"]) if state.get("effective_from") else None
    end = date.fromisoformat(state["effective_to"]) if state.get("effective_to") else None
    if as_of is not None:
        return (start is None or start <= as_of) and (end is None or as_of < end)
    if year is not None:
        return (start is None or start.year <= year) and (end is None or date(year, 1, 1) < end)
    return True


def check_premise(
    query: str, table: dict[str, Any], facts: QueryFacts | None = None, as_of: date | None = None
) -> dict[str, Any]:
    """Compare a question's claimed amount with the table's verified amounts.

    ``as_of`` (from the request) or a year named in the question limits the
    check to amounts in force then; an amount that was not yet in force is
    never quoted (verdict ``not_in_force``).
    """
    facts = facts or extract_facts(query)
    offence_id = facts.offence_id
    result = PremiseResult(
        verdict="not_checkable",
        offence_id=offence_id,
        jurisdiction=table.get("jurisdiction"),
        occurrence=facts.occurrence,
        claimed_inr=facts.claimed_inr[0] if facts.claimed_inr else None,
    )
    if offence_id is None:
        result.verdict = "ambiguous_offence" if facts.offences else "no_offence"
        return result.as_dict()
    if offence_id == "earphones":
        result.verdict = "not_named"
        return result.as_dict()
    if offence_id in LEGAL_REVIEW_OFFENCES:
        result.verdict = "legal_review"
        return result.as_dict()
    row = next((item for item in table.get("offences", []) if item["offence_id"] == offence_id), None)
    if row is None or row["state_compounding"]["status"] != "VERIFIED" or not row["state_compounding"]["amounts"]:
        result.verdict = "unverified"
        return result.as_dict()
    state = row["state_compounding"]
    if not _in_force(state, as_of, facts.year):
        result.verdict = "not_in_force"
        result.schedule_row = state.get("schedule_row")
        return result.as_dict()
    source = table["sources"][state["source_id"]]
    result.source = {"title": source["title"], "reference": source["notification_reference"], "url": source["url"]}
    result.schedule_row = state.get("schedule_row")
    applicable = [
        amount
        for amount in state["amounts"]
        if facts.occurrence is None or amount["occurrence"] in (facts.occurrence, "any")
    ] or state["amounts"]
    result.verified_amounts = applicable
    if result.claimed_inr is None:
        result.verdict = "no_claim"
    elif result.claimed_inr in {amount["inr"] for amount in applicable}:
        result.verdict = "supported"
    else:
        result.verdict = "contradicted"
    return result.as_dict()
