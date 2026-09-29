"""Freshness watch: have the official sources behind SETU changed?

Every source in data/traffic_offences/*.json pins the SHA-256 of the exact
file that was read, and so does every active source in the scheme corpus
manifests (corpus/manifests/*.json, M2.1). This script downloads each source
again and compares.

Most sources are compared byte for byte. Scheme web pages that differ on
every request (session tokens, visitor counters) are pinned on their
extracted text instead ("watch": "text"), using the corpus extractor and the
manifest's narrow ``ignore_lines``; that needs beautifulsoup4 and lxml.

    python scripts/freshness_watch.py [--summary FILE] [--json-out FILE]

Exit status
    0  every reachable source is unchanged
    1  at least one source changed, or every source was unreachable (then
       the watch itself is not working, for example the runner is blocked)
    2  the tables could not be read

A changed hash means a person must re-read the source before any amount is
trusted again. It does not mean the law changed: a re-scanned or re-signed
PDF also changes the bytes. Only hashes and metadata are kept in Git, never
source bodies. Byte comparisons use the standard library only; no secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "data" / "traffic_offences"
MANIFESTS = ROOT / "corpus" / "manifests"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MAX_BYTES = 50 * 1024 * 1024
TIMEOUT_SECONDS = 60
USER_AGENT = "SETU-freshness-watch/1.0 (+https://github.com/Rajdeep1212/setu-intelligence-workspace)"


class FetchError(Exception):
    """The source could not be downloaded; the reason is safe to print."""


@dataclass
class Source:
    url: str
    pinned_sha256: str
    used_by: list[str] = field(default_factory=list)
    mode: str = "bytes"  # bytes | text (hash of extracted text, see corpus/manifests)
    ignore_lines: list[str] = field(default_factory=list)


@dataclass
class Result:
    url: str
    status: str  # unchanged | changed | unreachable
    pinned_sha256: str
    current_sha256: str | None
    used_by: list[str]
    detail: str = ""


def load_sources(tables: Path = TABLES, manifests: Path = MANIFESTS) -> list[Source]:
    """Every distinct pinned source in the offence tables and the corpus manifests."""
    from ingestion.corpus_manifest import iter_active_sources, load_manifest, manifest_paths

    sources: dict[tuple[str, str], Source] = {}
    for path in sorted(tables.glob("*.json")):
        if path.name == "schema.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for source_id, source in data.get("sources", {}).items():
            key = (source["url"], source["sha256"])
            entry = sources.setdefault(key, Source(url=source["url"], pinned_sha256=source["sha256"]))
            entry.used_by.append(f"{path.name}:{source_id}")
    for path in manifest_paths(manifests):
        for _item, source in iter_active_sources(load_manifest(path)):
            pin = source["pin"]
            pinned = pin["text_sha256"] if pin["watch"] == "text" else pin["sha256"]
            entry = sources.setdefault(
                (source["official_url"], pinned),
                Source(source["official_url"], pinned, mode=pin["watch"], ignore_lines=list(pin.get("ignore_lines", []))),
            )
            entry.used_by.append(f"{path.name}:{source['source_id']}")
    return list(sources.values())


def fetch_bytes(url: str, timeout: float = TIMEOUT_SECONDS, max_bytes: int = MAX_BYTES) -> bytes:
    """The bytes served at url, read in blocks with a size cap."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    blocks = []
    size = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - https URLs from reviewed tables
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > max_bytes:
                    raise FetchError(f"larger than {max_bytes // (1024 * 1024)} MB")
                blocks.append(block)
    except urllib.error.HTTPError as error:
        raise FetchError(f"HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise FetchError(f"connection failed ({error.reason})") from None
    except TimeoutError:
        raise FetchError("timed out") from None
    except OSError as error:
        raise FetchError(f"connection error ({type(error).__name__})") from None
    return b"".join(blocks)


def fetch_sha256(url: str, timeout: float = TIMEOUT_SECONDS, max_bytes: int = MAX_BYTES) -> str:
    """SHA-256 of the bytes served at url."""
    return hashlib.sha256(fetch_bytes(url, timeout, max_bytes)).hexdigest()


def source_fingerprint(source: Source) -> str:
    """What the source's pin is compared with: its bytes, or its extracted text."""
    if source.mode == "bytes":
        return fetch_sha256(source.url)
    from ingestion.corpus_extract import ExtractionError, extract_html, text_fingerprint

    try:
        text = extract_html(fetch_bytes(source.url)).text
    except ExtractionError as error:
        raise FetchError(f"text could not be extracted ({error})") from None
    return text_fingerprint(text, source.ignore_lines)


def check(sources: list[Source], fetch: Callable[[str], str] | None = None) -> list[Result]:
    """Compare every source with its pin; ``fetch`` (url -> fingerprint) replaces the network in tests."""
    results = []
    for source in sources:
        try:
            current = fetch(source.url) if fetch else source_fingerprint(source)
        except FetchError as error:
            results.append(Result(source.url, "unreachable", source.pinned_sha256, None, source.used_by, str(error)))
            continue
        status = "unchanged" if current == source.pinned_sha256 else "changed"
        results.append(Result(source.url, status, source.pinned_sha256, current, source.used_by))
    return results


def exit_code(results: list[Result]) -> int:
    if any(result.status == "changed" for result in results):
        return 1
    if results and all(result.status == "unreachable" for result in results):
        return 1
    return 0


def summary_markdown(results: list[Result], checked_at: str) -> str:
    counts = {status: sum(r.status == status for r in results) for status in ("changed", "unreachable", "unchanged")}
    lines = [
        "## Source freshness watch",
        "",
        f"Checked {len(results)} pinned sources at {checked_at}: "
        f"{counts['changed']} changed, {counts['unreachable']} unreachable, {counts['unchanged']} unchanged.",
        "",
    ]
    if counts["changed"]:
        lines += [
            "**Changed sources must be re-read by a person before their amounts are trusted.** "
            "A new hash can also come from a re-scanned or re-signed file, so check the content, "
            "then update the pin (`sha256` and `retrieved_at`, or the manifest `pin`) where the source is used.",
            "",
        ]
    if results and counts["unreachable"] == len(results):
        lines += ["**No source could be reached, so nothing was checked.** The runner may be blocked.", ""]
    lines += ["| Status | Source | Used by | Detail |", "|---|---|---|---|"]
    order = {"changed": 0, "unreachable": 1, "unchanged": 2}
    for result in sorted(results, key=lambda r: (order[r.status], r.url)):
        detail = result.detail
        if result.status == "changed":
            detail = f"pinned {result.pinned_sha256[:12]}…, now {result.current_sha256[:12]}…"
        lines.append(f"| {result.status} | {result.url} | {', '.join(result.used_by)} | {detail} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, fetch: Callable[[str], str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summary", type=Path, help="append a Markdown summary to this file (e.g. $GITHUB_STEP_SUMMARY)")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    try:
        sources = load_sources()
    except (OSError, ValueError, KeyError) as error:
        print(f"could not read the offence tables or corpus manifests: {error}", file=sys.stderr)
        return 2
    if fetch is None and any(source.mode == "text" for source in sources):
        try:
            import bs4  # noqa: F401
            import lxml  # noqa: F401
        except ImportError:
            print("text-watched sources need beautifulsoup4 and lxml (see freshness.yml)", file=sys.stderr)
            return 2
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    results = check(sources, fetch)
    markdown = summary_markdown(results, checked_at)
    print(markdown)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(markdown)
    if args.json_out:
        report = {"schema": "setu.freshness-report/v1", "checked_at": checked_at, "results": [asdict(r) for r in results]}
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
