"""
PIB scraper — Week 1.

Fetches individual PIB press releases by Release ID (PRID) and, where
available, their English/Hindi/Bengali counterparts via the "Read this
release in:" links PIB attaches to every release.

IMPORTANT — read before running:
This module could not be tested against the live pib.gov.in site from the
build environment (network access there is restricted to package registries
and github). The URL pattern and language-link parsing below are confirmed
against real PIB pages, but the exact HTML container for the article body
can change between ministries/templates. Before a full run:
  1. `pip install requests beautifulsoup4 lxml`
  2. Run `fetch_release(PRID)` on 2-3 known PRIDs
  3. Open one of those URLs in a browser, inspect the article container in
     DevTools, and update CONTENT_SELECTORS below if the extracted text
     looks wrong (truncated, includes nav/footer junk, etc).

Usage pattern for the Week 1 MVP: don't try to crawl PIB's listing pages —
browse pib.gov.in yourself, pick ~20-30 releases relevant to schemes/policy
across ministries, note their PRIDs, and pass that list to `load_documents`.
Automating discovery is a good Week 5+ improvement once the pipeline works
end to end.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.pib.gov.in/PressReleasePage.aspx"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Try these, in order, as candidates for the main article container.
# Update this list once you've inspected a real page in DevTools.
CONTENT_SELECTORS = [
    {"id": "ContentPlaceHolder1_divPrintCont"},
    {"id": "ContentPlaceHolder1_pdet"},
    {"class_": "innner-page-main-about-us-content-right-part"},
    {"class_": "content-area"},
]

# "Read this release in: हिन्दी, Bengali, Gujarati, ..." — maps the visible
# link text PIB uses to our internal language codes. Extend as needed.
LANGUAGE_NAME_TO_CODE = {
    "हिन्दी": "hi",
    "hindi": "hi",
    "bengali": "bn",
    "bangla": "bn",
    "বাংলা": "bn",       # Bengali native script — used in PIB "Read this release in" links
    "বাঙলা": "bn",       # alternate Bengali spelling
    "english": "en",
}

logger = logging.getLogger(__name__)


def _clean_html(soup: BeautifulSoup) -> None:
    """Remove script, style, and noscript elements that would pollute extracted text."""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()


def _detect_language_from_script(text: str, min_threshold: int = 30) -> str:
    """
    Detect language from dominant Unicode script in text.

    Uses Unicode code point ranges — no external dependencies needed.
    Acts as a safety net to prevent mislabeling (e.g., English text
    stored as Bengali because of a wrong URL parameter).

    Returns 'hi', 'bn', 'en', or 'unknown'.
    """
    devanagari = bengali = latin = 0
    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F:
            devanagari += 1
        elif 0x0980 <= cp <= 0x09FF:
            bengali += 1
        elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
            latin += 1

    if devanagari > bengali and devanagari > min_threshold:
        return "hi"
    if bengali > devanagari and bengali > min_threshold:
        return "bn"
    if latin > 0:
        return "en"
    return "unknown"


@dataclass
class RawDocument:
    prid: str
    language: str
    title: str
    url: str
    posted_on: str | None
    raw_text: str
    related_prids: dict[str, str] = field(default_factory=dict)  # lang -> prid


def _extract_content_div(soup: BeautifulSoup):
    for selector in CONTENT_SELECTORS:
        div = soup.find("div", **selector)
        if div is not None and len(div.get_text(strip=True)) > 200:
            return div
    # Fallback: the <div> with the most visible text, excluding nav/footer.
    candidates = [
        d for d in soup.find_all("div")
        if d.find("nav") is None and d.find("footer") is None
    ]
    if not candidates:
        return soup
    return max(candidates, key=lambda d: len(d.get_text(strip=True)))


def _extract_related_prids(soup: BeautifulSoup) -> dict[str, str]:
    related: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "PressReleasePage.aspx" not in href and "PRID=" not in href:
            continue
        match = re.search(r"PRID=(\d+)", href)
        if not match:
            continue
        label = a.get_text(strip=True).lower()
        code = LANGUAGE_NAME_TO_CODE.get(label)
        if code:
            related[code] = match.group(1)
    return related


def fetch_release(prid: str, lang: int = 1, reg: int = 3, retries: int = 3) -> RawDocument:
    """
    Fetch and parse a single PIB press release.
    lang: 1=English, 2=Hindi (PIB's own numeric code — verify per-ministry,
          some templates vary). Bengali releases are usually reached via the
          "Read this release in" link on the English page rather than a
          fixed lang code, since not every release has a Bengali version.
    """
    url = f"{BASE_URL}?PRID={prid}&reg={reg}&lang={lang}"
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            break
        except requests.RequestException as exc:  # noqa: PERF203
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"Failed to fetch PRID={prid} after {retries} attempts") from last_error

    soup = BeautifulSoup(resp.text, "lxml")
    _clean_html(soup)

    title_tag = soup.find("meta", property="og:title") or soup.find("h1") or soup.find("h2")
    title = title_tag.get("content") if title_tag and title_tag.has_attr("content") else (
        title_tag.get_text(strip=True) if title_tag else f"PIB Release {prid}"
    )

    content_div = _extract_content_div(soup)
    raw_text = content_div.get_text("\n", strip=True)

    # Multi-language date extraction patterns
    date_patterns = [
        r"Posted On:\s*([^\n]+?)\s+by",                               # English
        r"(?:प्रकाशित|प्रविष्टि) तिथि:\s*([^\n]+?)(?:\s*द्वारा|\s*$)",  # Hindi
        r"পোস্ট করা হয়েছে:\s*([^\n]+?)(?:\s*$)",                         # Bengali
    ]
    posted_on = None
    for pattern in date_patterns:
        posted_match = re.search(pattern, raw_text, re.MULTILINE)
        if posted_match:
            posted_on = posted_match.group(1).strip()
            break

    # Detect language from actual text content, not just URL parameter.
    # This prevents the Bengali bug: fetching English pages labeled as Bengali.
    url_lang_hint = "hi" if lang == 2 else "en"
    detected_lang = _detect_language_from_script(raw_text)
    if detected_lang == "unknown":
        detected_lang = url_lang_hint

    return RawDocument(
        prid=str(prid),
        language=detected_lang,
        title=title,
        url=url,
        posted_on=posted_on,
        raw_text=raw_text,
        related_prids=_extract_related_prids(soup),
    )


def fetch_release_with_translations(prid: str, languages: tuple[str, ...] = ("en", "hi", "bn")) -> list[RawDocument]:
    """
    Fetch a release plus its Hindi/Bengali counterparts, if PIB links them.
    Useful for the Week 6 cross-lingual consistency checks — same underlying
    story, three language versions, one release family.
    """
    english = fetch_release(prid, lang=1)
    documents = [english] if "en" in languages else []

    for lang_code, related_prid in english.related_prids.items():
        if lang_code not in languages or lang_code == "en":
            continue
        try:
            lang_num = 2 if lang_code == "hi" else 1  # Bengali pages often reuse lang=1 in the URL
            doc = fetch_release(related_prid, lang=lang_num)
            # fetch_release now detects language from actual content via
            # _detect_language_from_script. If the detected language doesn't
            # match what we expected from the PIB translation link, skip it
            # rather than mislabeling the content.
            if doc.language != lang_code:
                logger.warning(
                    "PRID=%s: expected %s content but detected %s — skipping",
                    related_prid, lang_code, doc.language,
                )
                continue
            documents.append(doc)
        except RuntimeError:
            continue  # skip missing translations rather than failing the batch

    return documents


def load_documents(prids: list[str], languages: tuple[str, ...] = ("en", "hi", "bn")) -> list[RawDocument]:
    """Entry point used by ingest.py: fetch a curated list of PRIDs."""
    all_docs: list[RawDocument] = []
    for prid in prids:
        all_docs.extend(fetch_release_with_translations(prid, languages))
        time.sleep(1)  # be polite to a government server
    return all_docs
