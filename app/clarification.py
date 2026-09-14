"""Narrow, provider-free clarification rules for essential scheme distinctions."""

from __future__ import annotations

from app.grounding import query_language


FOCUSED_CLARIFICATIONS = {
    "student_credit_state": {
        "en": "Which state or Union Territory's student credit card scheme do you mean?",
        "hi": "आप किस राज्य या केंद्र शासित प्रदेश की स्टूडेंट क्रेडिट कार्ड योजना के बारे में पूछ रहे हैं?",
        "bn": "আপনি কোন রাজ্য বা কেন্দ্রশাসিত অঞ্চলের স্টুডেন্ট ক্রেডিট কার্ড প্রকল্পের কথা বলছেন?",
    },
    "insurance_type": {
        "en": "Do you mean life insurance through PMJJBY or accident insurance through PMSBY?",
        "hi": "क्या आपको PMJJBY का जीवन बीमा चाहिए या PMSBY का दुर्घटना बीमा?",
        "bn": "আপনি কি PMJJBY-এর জীবন বিমা, নাকি PMSBY-এর দুর্ঘটনা বিমা সম্পর্কে জানতে চান?",
    },
    "pension_jurisdiction": {
        "en": "Which state or Union Territory applies, and which old-age pension scheme do you mean?",
        "hi": "कौन-सा राज्य या केंद्र शासित प्रदेश लागू होता है, और आप किस वृद्धावस्था पेंशन योजना के बारे में पूछ रहे हैं?",
        "bn": "কোন রাজ্য বা কেন্দ্রশাসিত অঞ্চল প্রযোজ্য, এবং আপনি কোন বার্ধক্য পেনশন প্রকল্পের কথা বলছেন?",
    },
}


def focused_clarification(query: str, language: str | None = None) -> str | None:
    """Ask for one missing discriminator instead of assuming a scheme."""
    normalized = " ".join(query.casefold().split())
    has_west_bengal = any(
        value in normalized
        for value in ("west bengal", "पश्चिम बंगाल", "পশ্চিমবঙ্গ")
    )
    clarification: str | None = None
    if "student credit card" in normalized and not has_west_bengal:
        clarification = "student_credit_state"
    elif "pmjjby" in normalized and "pmsby" in normalized and not any(
        value in normalized
        for value in (
            "life insurance",
            "accident insurance",
            "जीवन बीमा",
            "दुर्घटना बीमा",
            "জীবন বিমা",
            "দুর্ঘটনা বিমা",
        )
    ):
        clarification = "insurance_type"
    elif (
        "old age pension" in normalized
        or "old-age pension" in normalized
        or (
            "পেনশন" in normalized
            and any(value in normalized for value in ("বয়স্ক", "বার্ধক্য"))
        )
    ) and not any(
        value in normalized
        for value in (
            "jai johar",
            "taposili bandhu",
            "জয় জোহর",
            "তপশিলি বন্ধু",
            "जय जोहार",
            "तपोसिली बंधु",
        )
    ):
        clarification = "pension_jurisdiction"
    if clarification is None:
        return None
    return FOCUSED_CLARIFICATIONS[clarification][query_language(query, language)]
