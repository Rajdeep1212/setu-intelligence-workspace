"""Structure-preserving extraction and chunking for official source documents."""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup


EXTRACTION_VERSION = "setu-structured-v2"
CHUNKING_VERSION = "setu-structure-aware-v1"
_SPACE = re.compile(r"[ \t\f\v]+")
_BLANKS = re.compile(r"\n{3,}")
_LOCATION = re.compile(r"^(?:\[Page \d+\]|#{1,6}\s+.+)$")


class ExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractedDocument:
    title: str | None
    text: str
    location_count: int
    page_count: int | None


def extract_document(content: bytes, content_type: str) -> ExtractedDocument:
    if content.startswith(b"%PDF-") or content_type == "application/pdf":
        return extract_pdf(content)
    if content_type in {"text/html", "application/xhtml+xml"}:
        return extract_html(content)
    if content_type == "text/plain":
        text = content.decode("utf-8", errors="replace")
        return ExtractedDocument(None, _normalize_text(text), 0, None)
    raise ExtractionError(f"No extractor for Content-Type {content_type!r}")


def extract_html(content: bytes) -> ExtractedDocument:
    soup = BeautifulSoup(content, "lxml")
    for node in soup(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
            "svg",
            "canvas",
            "iframe",
            "input",
            "button",
            "select",
            "textarea",
        ]
    ):
        node.decompose()
    title = _clean_line(soup.title.get_text(" ", strip=True)) if soup.title else None
    candidates = [
        node
        for selector in ("main", "article", "[role=main]")
        for node in soup.select(selector)
    ]
    body = soup.body or soup
    best_candidate = (
        max(candidates, key=lambda node: len(node.get_text(" ", strip=True)))
        if candidates
        else None
    )
    # Some official portals ship an empty client-rendering mount in <main> while
    # keeping their accessible public copy elsewhere in <body>.  Prefer semantic
    # content only when it contains enough text to be meaningful.
    root = (
        best_candidate
        if best_candidate is not None
        and len(best_candidate.get_text(" ", strip=True)) >= 200
        else body
    )

    lines: list[str] = []
    structural_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd", "tr"}
    for node in root.find_all(structural_tags):
        if any(parent.name in structural_tags for parent in node.parents if parent is not root):
            continue
        text = _clean_line(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name.startswith("h"):
            level = min(int(node.name[1]), 6)
            lines.append(f"{'#' * level} {text}")
        elif node.name == "li":
            lines.append(f"- {text}")
        elif node.name == "tr":
            cells = [_clean_line(cell.get_text(" ", strip=True)) for cell in node.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            if cells:
                lines.append(" | ".join(cells))
        else:
            lines.append(text)

    if not lines:
        lines = [_clean_line(root.get_text("\n", strip=True))]
    text = _normalize_text("\n\n".join(_deduplicate_adjacent(lines)))
    return ExtractedDocument(
        title=title,
        text=text,
        location_count=sum(bool(_LOCATION.match(line)) for line in text.splitlines()),
        page_count=None,
    )


def extract_pdf(content: bytes, *, max_pages: int = 500) -> ExtractedDocument:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ExtractionError(
            "PDF extraction requires pypdf; install requirements-corpus.txt"
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
    except Exception as exc:
        raise ExtractionError(f"Cannot parse PDF: {exc}") from exc
    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0:
                raise ExtractionError("Encrypted PDF cannot be opened without a password")
        except Exception as exc:
            raise ExtractionError("Encrypted PDF cannot be opened") from exc
    if not reader.pages:
        raise ExtractionError("PDF has no pages")
    if len(reader.pages) > max_pages:
        raise ExtractionError(f"PDF has {len(reader.pages)} pages; limit is {max_pages}")

    sections: list[str] = []
    extracted_pages = 0
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = _normalize_text(page.extract_text() or "")
        except Exception as exc:
            raise ExtractionError(f"Failed extracting PDF page {page_number}: {exc}") from exc
        if not page_text:
            continue
        extracted_pages += 1
        sections.append(f"[Page {page_number}]\n\n{page_text}")
    if not sections:
        raise ExtractionError("PDF contains no machine-extractable text")
    title = None
    metadata = reader.metadata
    if metadata and metadata.title:
        title = _clean_line(str(metadata.title))
    return ExtractedDocument(
        title=title,
        text="\n\n".join(sections),
        location_count=extracted_pages,
        page_count=len(reader.pages),
    )


def validate_extraction(
    extracted: ExtractedDocument,
    required_markers: Iterable[str],
    *,
    min_characters: int = 500,
    max_characters: int = 2_000_000,
) -> dict[str, float | int]:
    text = extracted.text
    if len(text) < min_characters:
        raise ExtractionError(
            f"Extracted text has {len(text)} characters; minimum is {min_characters}"
        )
    if len(text) > max_characters:
        raise ExtractionError(
            f"Extracted text has {len(text)} characters; maximum is {max_characters}"
        )
    folded = unicodedata.normalize("NFKC", text).casefold()
    missing = [marker for marker in required_markers if unicodedata.normalize("NFKC", marker).casefold() not in folded]
    if missing:
        raise ExtractionError(f"Required source markers are missing: {missing}")
    replacement_ratio = text.count("\ufffd") / max(len(text), 1)
    control_count = sum(
        unicodedata.category(character) == "Cc" and character not in "\n\r\t"
        for character in text
    )
    control_ratio = control_count / max(len(text), 1)
    if replacement_ratio > 0.005:
        raise ExtractionError(f"Replacement-character ratio is too high: {replacement_ratio:.4f}")
    if control_ratio > 0.001:
        raise ExtractionError(f"Control-character ratio is too high: {control_ratio:.4f}")
    word_count = len(re.findall(r"\w+", text, flags=re.UNICODE))
    if word_count < 80:
        raise ExtractionError(f"Extracted text has only {word_count} word-like tokens")
    return {
        "character_count": len(text),
        "word_count": word_count,
        "location_count": extracted.location_count,
        "page_count": extracted.page_count or 0,
        "replacement_ratio": replacement_ratio,
        "control_ratio": control_ratio,
    }


def chunk_structured_text(
    text: str,
    *,
    target_characters: int = 1_200,
    overlap_characters: int = 120,
) -> list[str]:
    if target_characters < 300:
        raise ValueError("target_characters must be at least 300")
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    chunks: list[str] = []
    location: str | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        body = "\n\n".join(current).strip()
        if body and (not location or not body.startswith(location)):
            body = f"{location}\n\n{body}" if location else body
        if body:
            chunks.append(body)
        tail = body[-overlap_characters:].lstrip() if overlap_characters else ""
        current = [f"…{tail}"] if tail else []

    for block in blocks:
        first_line = block.splitlines()[0].strip()
        if _LOCATION.match(first_line):
            if current:
                flush()
                current = []
            location = first_line
            remainder = "\n".join(block.splitlines()[1:]).strip()
            if not remainder:
                continue
            block = remainder
        for part in _split_long_block(block, target_characters):
            candidate = "\n\n".join(current + [part])
            prefix_length = len(location) + 2 if location else 0
            if current and len(candidate) + prefix_length > target_characters:
                flush()
            current.append(part)
    flush()
    return [chunk for chunk in chunks if len(chunk) >= 80]


def _split_long_block(block: str, limit: int) -> list[str]:
    if len(block) <= limit:
        return [block]
    parts: list[str] = []
    remaining = block
    while len(remaining) > limit:
        split_at = max(
            remaining.rfind(". ", 0, limit),
            remaining.rfind("। ", 0, limit),
            remaining.rfind(" ", 0, limit),
        )
        if split_at < limit // 2:
            split_at = limit
        else:
            split_at += 1
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def _clean_line(value: str) -> str:
    return _SPACE.sub(" ", value).strip()


def _normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "\n".join(_clean_line(line) for line in value.splitlines())
    return _BLANKS.sub("\n\n", value).strip()


def _deduplicate_adjacent(lines: Iterable[str]) -> list[str]:
    output: list[str] = []
    for line in lines:
        if not output or output[-1] != line:
            output.append(line)
    return output
