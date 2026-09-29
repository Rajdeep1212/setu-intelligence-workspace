"""Scam Shield: a deterministic check for pasted messages and links (Phase 4).

Fake e-challan messages with payment links, APKs and look-alike Parivahan
sites are a current, officially reported problem (PIB Fact Check, 10 Jul 2026;
Kerala Police, 26 Sep 2026; Maharashtra Transport Department). This module
reads a pasted SMS, WhatsApp message or link and reports warning signs. It
never calls a model and never says a message is "safe": the best it can say
is that a link goes to an official government domain.

Official domains are recognised structurally: hosts ending in ``.gov.in``
(registrable only by government organisations, through NIC) or ``.nic.in``
(NIC). Evidence for every rule and warning is in data/scam_shield/sources.json.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SOURCES_PATH = Path(__file__).resolve().parents[2] / "data" / "scam_shield" / "sources.json"

HIGH_RISK = {
    "impersonating_domain", "apk", "asks_for_secret", "payment_link_not_official", "payment_to_personal_upi",
    "matches_debunk", "ip_address_link",
}
MEDIUM_RISK = {"shortened_link", "punycode_domain", "urgency", "http_link"}
# Informational only: a non-government link (a news site, say) is not a warning sign by itself.
INFO = {"unofficial_link"}

_SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "cutt.ly", "rb.gy", "is.gd", "shorturl.at", "tiny.cc",
    "ow.ly", "rebrand.ly", "s.id", "t.ly", "shorturl.asia", "bitly.com", "v.gd", "clck.ru", "urlz.fr",
}
# Government or service names a fake site borrows. Short tokens must be a whole
# label ("gov", "rto"); long tokens may appear inside a label ("echallanpay").
_SHORT_TOKENS = {"gov", "govt", "nic", "rto", "npci"}
_LONG_TOKENS = {
    "parivahan", "echallan", "e-challan", "challan", "vahan", "sarathi", "mparivahan", "trafficpolice",
    "traffic-police", "pmkisan", "pm-kisan", "myscheme", "digilocker", "uidai", "aadhaar", "incometax",
    "fastag", "nhai",
    # Scheme names. MNRE's PM-KUSUM warning names kusumyojanaonline.in.net (FINDINGS C7).
    "yojana", "pmkusum", "pm-kusum", "pmay", "ayushman", "pmjay", "epfo",
}
# Second-level suffixes sold commercially that read like an Indian domain.
_LOOKALIKE_SUFFIXES = (".in.net", ".gov.in.net", ".in.com")
_TLDS = (
    "com|in|net|org|info|online|site|xyz|top|live|app|link|co|me|io|club|shop|store|cc|icu|vip|buzz|pro|"
    "ly|gl|gd|at|to|id|ru|fr|asia|tk|ml|ga|cf|gq|work|click|support|help|website|space|fun|today"
)
_URL_PATTERN = re.compile(
    rf"(?:https?://[^\s<>\"']+|www\.[^\s<>\"']+|(?<![@\w.-])(?:[a-z0-9-]+\.)+(?:{_TLDS})(?::\d+)?(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
_IP_URL = re.compile(r"https?://\d{1,3}(?:\.\d{1,3}){3}[^\s]*", re.IGNORECASE)

_CHALLAN = ("challan", "e-challan", "traffic violation", "fine", "penalty", "चालान", "जुर्माना", "চালান", "জরিমানা")
_PAY = ("pay", "payment", "upi", "click", "clear", "settle", "भुगतान", "पे करें", "पेमेंट", "জমা", "পেমেন্ট", "পরিশোধ")
_SECRET = re.compile(r"\b(?:otp|pin|cvv|password|upi pin|mpin)\b|ओटीपी|पासवर्ड|पिन नंबर|ওটিপি|পাসওয়ার্ড|পিন নম্বর", re.IGNORECASE)
# A UPI ID such as name@ybl. Official challans are paid on the e-challan portal, not to a person.
_UPI_ID = re.compile(r"(?<![\w.])[\w.-]{2,}@(?:ybl|okaxis|oksbi|okhdfcbank|okicici|paytm|upi|apl|ibl|axl|icici|sbi|hdfcbank|kotak|yesbank|axisbank|freecharge|jio|airtel|ptyes|ptsbi|pthdfc|ptaxis)(?![\w.])", re.IGNORECASE)
_APK = re.compile(r"\.apk\b|\bapk\b|एपीके|এপিকে", re.IGNORECASE)
_URGENCY = (
    "immediately", "urgent", "today", "within 24 hours", "last date", "last chance", "suspend", "suspended",
    "seized", "blocked", "legal action", "arrest", "will be cancelled", "court",
    "तुरंत", "आज ही", "अंतिम तिथि", "निलंबित", "जब्त", "कानूनी कार्रवाई", "रद्द",
    "অবিলম্বে", "আজই", "শেষ তারিখ", "বাতিল", "জব্দ", "আইনি ব্যবস্থা",
)
_ASK_ABOUT_MESSAGE = re.compile(
    r"(message|sms|text|link|website|site|call|whatsapp|मैसेज|संदेश|लिंक|वेबसाइट|মেসেজ|বার্তা|লিঙ্ক|ওয়েবসাইট)",
    re.IGNORECASE,
)
_ASK_GENUINE = re.compile(
    r"(fake|real|genuine|scam|fraud|legit|phishing|फर्जी|फ़र्ज़ी|असली|धोखा|ठगी|ভুয়া|আসল|প্রতারণা|জালিয়াতি)",
    re.IGNORECASE,
)


@dataclass
class LinkReport:
    url: str
    host: str
    official: bool
    kinds: list[str] = field(default_factory=list)


@dataclass
class ScamReport:
    verdict: str
    signals: list[str]
    links: list[LinkReport]
    debunks: list[dict[str, Any]]
    hosts_by_signal: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "signals": self.signals,
            "links": [{"url": link.url, "host": link.host, "official": link.official, "kinds": link.kinds} for link in self.links],
            "debunks": [
                {key: debunk[key] for key in ("id", "kind", "topic", "summary", "date", "issuer", "source")}
                for debunk in self.debunks
            ],
        }


@lru_cache(maxsize=1)
def load_sources() -> dict[str, Any]:
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))


def _contains(text: str, term: str) -> bool:
    if term.isascii():
        return re.search(rf"(?<![a-z]){re.escape(term)}", text) is not None
    return term in text


def is_official_host(host: str) -> bool:
    return host in ("gov.in", "nic.in") or host.endswith(".gov.in") or host.endswith(".nic.in")


def _host_of(raw: str) -> str:
    candidate = raw if re.match(r"https?://", raw, re.IGNORECASE) else f"http://{raw}"
    host = (urlsplit(candidate).hostname or "").rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def extract_links(text: str) -> list[str]:
    found = []
    for match in _URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(".,;:!?)]}'\"")
        if url and url not in found:
            found.append(url)
    return found


def _impersonates(host: str) -> bool:
    labels = re.split(r"[.-]", host)
    body = host.rsplit(".", 1)[0]
    return (
        any(token in labels for token in _SHORT_TOKENS)
        or any(token in body for token in _LONG_TOKENS)
        or host.endswith(_LOOKALIKE_SUFFIXES)
    )


def _link_report(url: str) -> LinkReport:
    host = _host_of(url)
    report = LinkReport(url=url, host=host, official=is_official_host(host))
    try:
        ipaddress.ip_address(host)
        report.kinds.append("ip_address_link")
        report.official = False
    except ValueError:
        pass
    if any(label.startswith("xn--") for label in host.split(".")):
        report.kinds.append("punycode_domain")
    if host in _SHORTENERS:
        report.kinds.append("shortened_link")
    if urlsplit(url if "://" in url else f"http://{url}").path.lower().endswith(".apk"):
        report.kinds.append("apk")
    if not report.official:
        report.kinds.append("impersonating_domain" if _impersonates(host) else "unofficial_link")
    if url.lower().startswith("http://") and not report.official:
        report.kinds.append("http_link")
    return report


def _matching_debunks(normalized: str) -> list[dict[str, Any]]:
    matches = []
    for debunk in load_sources()["debunks"]:
        if all(any(_contains(normalized, term) for term in group) for group in debunk["match_all"]) and all(
            any(_contains(normalized, term) for term in group) for group in debunk["match_any"]
        ):
            matches.append(debunk)
    return matches


def should_check(text: str) -> bool:
    """Whether a query is a message or link to screen, rather than a question to answer."""
    normalized = " ".join(text.casefold().split())
    if extract_links(text) or _APK.search(normalized) or _SECRET.search(normalized) or _UPI_ID.search(normalized):
        return True
    return bool(_ASK_ABOUT_MESSAGE.search(normalized) and _ASK_GENUINE.search(normalized))


def check_message(text: str) -> ScamReport:
    normalized = " ".join(text.casefold().split())
    links = [_link_report(url) for url in extract_links(text)]
    signals: list[str] = []
    hosts: dict[str, str] = {}

    def add(code: str, host: str = "") -> None:
        if code not in signals:
            signals.append(code)
            if host:
                hosts[code] = host

    for link in links:
        for kind in link.kinds:
            add(kind, link.host)
    if _APK.search(normalized):
        add("apk")
    if _SECRET.search(normalized):
        add("asks_for_secret")
    mentions_challan = any(_contains(normalized, term) for term in _CHALLAN)
    mentions_pay = any(_contains(normalized, term) for term in _PAY)
    unofficial = [link for link in links if not link.official]
    if mentions_challan and mentions_pay and unofficial:
        add("payment_link_not_official", unofficial[0].host)
    upi = _UPI_ID.search(normalized)
    if upi and (mentions_challan or mentions_pay):
        add("payment_to_personal_upi", upi.group(0))
    if any(_contains(normalized, term) for term in _URGENCY):
        add("urgency")
    debunks = _matching_debunks(normalized)
    # A false claim is a warning sign on its own. A warning about fake channels
    # (links, apps) counts only when this message actually uses one; otherwise
    # it is shown as related context, so a genuine official message is not flagged.
    uses_risky_channel = any(signal in signals for signal in ("apk", "asks_for_secret", "ip_address_link", "shortened_link", "punycode_domain")) or bool(unofficial)
    if any(debunk.get("kind") == "false_claim" for debunk in debunks) or (debunks and uses_risky_channel):
        add("matches_debunk")

    if any(signal in HIGH_RISK for signal in signals):
        verdict = "likely_scam"
    elif any(signal in MEDIUM_RISK for signal in signals):
        verdict = "suspicious"
    elif links and all(link.official for link in links):
        verdict = "official_link"
    else:
        verdict = "no_warning_signs"
    order = [code for code in (*sorted(HIGH_RISK), *sorted(MEDIUM_RISK), *sorted(INFO)) if code in signals]
    return ScamReport(verdict=verdict, signals=order, links=links, debunks=debunks, hosts_by_signal=hosts)


TEXT = {
    "en": {
        "likely_scam": "This looks like a scam.",
        "suspicious": "Be careful: this message has warning signs.",
        "official_link": "The link goes to an official government domain ({host}). SETU still cannot confirm that the message itself is genuine.",
        "no_warning_signs": "SETU found no warning signs, but it cannot confirm that this message is genuine.",
        "impersonating_domain": "The link ({host}) borrows a government or service name but is not a .gov.in or .nic.in address.",
        "apk": "It asks you to install an app file (APK). Police and transport departments warn never to install apps sent in messages.",
        "asks_for_secret": "It asks for an OTP, PIN or password. Genuine authorities do not ask for these through messages or links.",
        "payment_link_not_official": "It asks you to pay a challan or fine through a link that is not an official government address.",
        "payment_to_personal_upi": "It asks you to pay to a personal UPI ID ({host}). Challans are paid through the official e-challan portal.",
        "ip_address_link": "The link uses a raw number address instead of a website name.",
        "shortened_link": "The link is shortened ({host}), which hides where it really goes.",
        "punycode_domain": "The link uses look-alike characters in its address ({host}).",
        "unofficial_link": "The link ({host}) is not a government address.",
        "urgency": "It pressures you with deadlines or threats such as suspension or seizure.",
        "http_link": "The link is not encrypted (http).",
        "debunk": "{issuer} warned about this ({date}): {topic}.",
        "related": "Related warning from {issuer} ({date}): {topic}.",
        "advice": "Do not tap links or install apps from messages. Check challans only at echallan.parivahan.gov.in, typing the address yourself. Never share an OTP or PIN. If you have paid or shared details, call 1930 or report at cybercrime.gov.in.",
    },
    "hi": {
        "likely_scam": "यह धोखाधड़ी लगता है।",
        "suspicious": "सावधान रहें: इस संदेश में चेतावनी के संकेत हैं।",
        "official_link": "लिंक एक आधिकारिक सरकारी डोमेन ({host}) पर जाता है। फिर भी SETU यह पुष्टि नहीं कर सकता कि संदेश स्वयं असली है।",
        "no_warning_signs": "SETU को कोई चेतावनी संकेत नहीं मिला, पर वह पुष्टि नहीं कर सकता कि यह संदेश असली है।",
        "impersonating_domain": "लिंक ({host}) किसी सरकारी या सेवा के नाम का इस्तेमाल करता है, पर यह .gov.in या .nic.in पता नहीं है।",
        "apk": "यह आपसे ऐप फ़ाइल (APK) इंस्टॉल करने को कहता है। पुलिस और परिवहन विभाग चेतावनी देते हैं कि संदेश में आए ऐप कभी इंस्टॉल न करें।",
        "asks_for_secret": "यह OTP, PIN या पासवर्ड माँगता है। असली अधिकारी संदेश या लिंक से ये नहीं माँगते।",
        "payment_link_not_official": "यह चालान या जुर्माना ऐसे लिंक से भरने को कहता है जो आधिकारिक सरकारी पता नहीं है।",
        "payment_to_personal_upi": "यह किसी निजी UPI ID ({host}) पर भुगतान करने को कहता है। चालान आधिकारिक ई-चालान पोर्टल से भरे जाते हैं।",
        "ip_address_link": "लिंक वेबसाइट के नाम की जगह सीधे नंबर वाला पता इस्तेमाल करता है।",
        "shortened_link": "लिंक छोटा किया गया है ({host}), जिससे असली पता छिप जाता है।",
        "punycode_domain": "लिंक के पते में मिलते-जुलते अक्षर हैं ({host})।",
        "unofficial_link": "लिंक ({host}) सरकारी पता नहीं है।",
        "urgency": "यह समय-सीमा या निलंबन, ज़ब्ती जैसी धमकियों से दबाव बनाता है।",
        "http_link": "लिंक एन्क्रिप्टेड नहीं है (http)।",
        "debunk": "{issuer} ने इसके बारे में चेतावनी दी थी ({date}): {topic}।",
        "related": "{issuer} की संबंधित चेतावनी ({date}): {topic}।",
        "advice": "संदेशों में आए लिंक पर टैप न करें और कोई ऐप इंस्टॉल न करें। चालान केवल echallan.parivahan.gov.in पर, पता ख़ुद टाइप करके जाँचें। OTP या PIN कभी साझा न करें। अगर आपने भुगतान किया है या जानकारी साझा की है, तो 1930 पर कॉल करें या cybercrime.gov.in पर शिकायत करें।",
    },
    "bn": {
        "likely_scam": "এটি প্রতারণা বলে মনে হচ্ছে।",
        "suspicious": "সাবধান: এই বার্তায় সতর্কতার চিহ্ন আছে।",
        "official_link": "লিঙ্কটি একটি সরকারি ডোমেনে ({host}) যায়। তবুও SETU নিশ্চিত করতে পারে না যে বার্তাটি নিজে আসল।",
        "no_warning_signs": "SETU কোনো সতর্কতার চিহ্ন পায়নি, কিন্তু বার্তাটি আসল কি না তা নিশ্চিত করতে পারে না।",
        "impersonating_domain": "লিঙ্কটি ({host}) সরকারি বা পরিষেবার নাম ব্যবহার করে, কিন্তু এটি .gov.in বা .nic.in ঠিকানা নয়।",
        "apk": "এটি একটি অ্যাপ ফাইল (APK) ইনস্টল করতে বলে। পুলিশ ও পরিবহণ দপ্তর সতর্ক করে যে বার্তায় পাঠানো অ্যাপ কখনও ইনস্টল করবেন না।",
        "asks_for_secret": "এটি OTP, PIN বা পাসওয়ার্ড চায়। আসল কর্তৃপক্ষ বার্তা বা লিঙ্কে এগুলি চায় না।",
        "payment_link_not_official": "এটি এমন লিঙ্কে চালান বা জরিমানা জমা দিতে বলে যা সরকারি ঠিকানা নয়।",
        "payment_to_personal_upi": "এটি একটি ব্যক্তিগত UPI ID-তে ({host}) টাকা দিতে বলে। চালান সরকারি ই-চালান পোর্টালে জমা দেওয়া হয়।",
        "ip_address_link": "লিঙ্কটি ওয়েবসাইটের নামের বদলে শুধু সংখ্যার ঠিকানা ব্যবহার করে।",
        "shortened_link": "লিঙ্কটি ছোট করা ({host}), তাই আসল ঠিকানা লুকিয়ে থাকে।",
        "punycode_domain": "লিঙ্কের ঠিকানায় দেখতে একই রকম অক্ষর আছে ({host})।",
        "unofficial_link": "লিঙ্কটি ({host}) সরকারি ঠিকানা নয়।",
        "urgency": "এটি সময়সীমা বা বাতিল, জব্দের মতো হুমকি দিয়ে চাপ দেয়।",
        "http_link": "লিঙ্কটি এনক্রিপ্ট করা নয় (http)।",
        "debunk": "{issuer} এ বিষয়ে সতর্ক করেছিল ({date}): {topic}।",
        "related": "{issuer}-এর সম্পর্কিত সতর্কবার্তা ({date}): {topic}।",
        "advice": "বার্তার লিঙ্কে ট্যাপ করবেন না বা কোনো অ্যাপ ইনস্টল করবেন না। চালান শুধু echallan.parivahan.gov.in-এ, ঠিকানা নিজে টাইপ করে দেখুন। কখনও OTP বা PIN শেয়ার করবেন না। টাকা দিয়ে থাকলে বা তথ্য শেয়ার করলে 1930-এ ফোন করুন বা cybercrime.gov.in-এ অভিযোগ জানান।",
    },
}


MAX_SECTIONS = 12  # QueryResponse.sections max_length


def _fit_sections(sentences: list[str]) -> list[str]:
    """Keep every sentence while staying within the API's section limit."""
    if len(sentences) <= MAX_SECTIONS:
        return sentences
    return sentences[: MAX_SECTIONS - 1] + [" ".join(sentences[MAX_SECTIONS - 1 :])]


def compose(text: str, language: str) -> dict[str, Any]:
    """Agent state update for a screened message."""
    report = check_message(text)
    words = TEXT[language]
    official_host = next((link.host for link in report.links if link.official), "")
    sentences = [words[report.verdict].format(host=official_host)]
    for signal in report.signals:
        if signal == "matches_debunk":
            continue
        sentences.append(words[signal].format(host=report.hosts_by_signal.get(signal, "")))
    template = words["debunk"] if "matches_debunk" in report.signals else words["related"]
    for debunk in report.debunks:
        sentences.append(template.format(issuer=debunk["issuer"], date=debunk["date"], topic=debunk["topic"]))
    sentences.append(words["advice"])
    return {
        "answer": " ".join(sentences),
        "sections": [{"text": sentence, "citation_ids": []} for sentence in _fit_sections(sentences)],
        "citations": [],
        "confidence": None,
        "route": "scam_check",
        "response_status": "scam_check",
        "scam_check": report.as_dict(),
    }
