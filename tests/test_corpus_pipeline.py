"""M2.1: scheme corpus pipeline (manifests, safe fetching, extraction, staging).

Offline: HTTP responses, DNS, the embedding model and the database are fakes.
The real manifests in corpus/manifests are only read, never fetched. The
PostgreSQL path (migrations 0001 and 0002 in a staging database) is covered
in test_migrations_postgres.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from ingestion import corpus_manifest as cm
from ingestion import corpus_pipeline as pipeline
from ingestion import corpus_state
from ingestion import staging_db
from ingestion.corpus_extract import (
    EXTRACTION_VERSION,
    ExtractionError,
    chunk_structured_text,
    extract_document,
    extract_html,
    text_fingerprint,
    validate_extraction,
)
from ingestion.safe_fetch import FetchError, ResponseLimitError, SafeHttpFetcher, UnsafeUrlError

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "corpus" / "manifests"

PAGE = (
    "<html><head><title>Scheme page</title></head><body>"
    "<nav>Home | Login</nav>"
    "<main><h1>Example Yojana</h1>"
    + "".join(f"<p>Paragraph {n} of the official Example Yojana guidelines describes the benefit process.</p>" for n in range(30))
    + "<p>Total Visitors: 1234</p></main>"
    "<footer>Copyright</footer></body></html>"
).encode("utf-8")
PAGE_SHA = hashlib.sha256(PAGE).hexdigest()


def _minimal_pdf(text: str) -> bytes:
    """A one-page PDF with a real text stream, built with correct xref offsets."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _text_pin(content: bytes, ignore_lines=()) -> str:
    return text_fingerprint(extract_html(content).text, ignore_lines)


def _manifest(**source_overrides) -> dict:
    source = {
        "source_id": "example.portal.current",
        "document_title": "Example Yojana portal",
        "document_identifier": None,
        "source_type": "official_portal",
        "official_url": "https://example.gov.in/scheme",
        "publisher": "Department of Examples, Government of India",
        "publication_date": None,
        "updated_date": "2026-02-17",
        "effective_from": "2015-06-01",
        "language": "en",
        "jurisdiction": "IN",
        "source_status": "current official page",
        "coverage_scope": "Benefit and process.",
        "required_markers": ["Example Yojana"],
        "min_extracted_characters": 500,
        "pin": {
            "sha256": PAGE_SHA,
            "retrieved_at": "2026-09-09T06:57:17Z",
            "watch": "text",
            "text_sha256": _text_pin(PAGE, ["^Total Visitors: \\d+$"]),
            "text_version": EXTRACTION_VERSION,
            "ignore_lines": ["^Total Visitors: \\d+$"],
        },
    }
    source.update(source_overrides)
    return {
        "schema_version": 2,
        "batch_id": "batch-test",
        "title": "Test batch",
        "reviewed_on": "2026-09-09",
        "fetch_policy": {"allowed_hosts": ["example.gov.in"]},
        "items": [
            {
                "stable_id": "scheme.central.example",
                "canonical_title": "Example Yojana",
                "item_type": "central_scheme",
                "category": "income_support",
                "jurisdiction": "IN",
                "publisher": "Department of Examples, Government of India",
                "current_status": "active official scheme page",
                "status_as_of": "2026-09-09",
                "official_application_url": "https://example.gov.in/apply",
                "sources": [source],
                "retrieval_checks": [
                    {
                        "check_id": "example.en.benefit",
                        "query": "What does Example Yojana provide?",
                        "query_language": "en",
                        "expected_rank_max": 3,
                        "expected_passage_markers": ["benefit process"],
                    }
                ],
            }
        ],
    }


def public_resolver(host, port, type):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


class FakeResponse:
    def __init__(self, status_code=200, body=b"ok", headers=None):
        self.status_code = status_code
        self.body = body
        self.headers = headers if headers is not None else {"Content-Type": "text/plain"}

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start : start + chunk_size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        assert kwargs["allow_redirects"] is False
        self.urls.append(url)
        return self.responses.pop(0)


def _fetcher(responses, resolver=public_resolver, **kwargs):
    session = FakeSession(responses)
    fetcher = SafeHttpFetcher(
        ["example.gov.in", "www.example.gov.in"],
        session=session,
        resolver=resolver,
        min_host_interval=0,
        retries=0,
        **kwargs,
    )
    return fetcher, session


class SafeFetchTests(unittest.TestCase):
    def test_only_https_on_exact_allowlisted_hosts(self):
        fetcher, _ = _fetcher([])
        for url in (
            "http://example.gov.in/x",
            "https://evil.example.gov.in.attacker.com/x",
            "https://notexample.gov.in/x",
            "https://user:pw@example.gov.in/x",
            "https://example.gov.in:8443/x",
        ):
            with self.subTest(url=url), self.assertRaises(UnsafeUrlError):
                fetcher.fetch(url)

    def test_rejects_private_dns_target_even_when_host_is_allowlisted(self):
        fetcher, session = _fetcher([], resolver=lambda *a, **k: [(2, 1, 6, "", ("10.0.0.5", 443))])
        with self.assertRaisesRegex(UnsafeUrlError, "non-global"):
            fetcher.fetch("https://example.gov.in/x")
        self.assertEqual(session.urls, [])

    def test_every_redirect_is_checked_against_the_allowlist(self):
        fetcher, session = _fetcher([FakeResponse(302, headers={"Location": "https://attacker.example.com/x"})])
        with self.assertRaises(UnsafeUrlError):
            fetcher.fetch("https://example.gov.in/x")
        self.assertEqual(session.urls, ["https://example.gov.in/x"])

    def test_follows_allowlisted_redirect_and_reports_final_url(self):
        fetcher, _ = _fetcher(
            [
                FakeResponse(301, headers={"Location": "https://www.example.gov.in/x"}),
                FakeResponse(200, PAGE, {"Content-Type": "text/html; charset=utf-8"}),
            ]
        )
        result = fetcher.fetch("https://example.gov.in/x")
        self.assertEqual(result.final_url, "https://www.example.gov.in/x")
        self.assertEqual(result.content_type, "text/html")
        self.assertEqual(result.content, PAGE)

    def test_stops_a_stream_that_exceeds_the_size_limit(self):
        fetcher, _ = _fetcher([FakeResponse(200, b"x" * 2048, {"Content-Type": "text/plain"})], max_bytes=1024)
        with self.assertRaises(ResponseLimitError):
            fetcher.fetch("https://example.gov.in/x")

    def test_rejects_unknown_content_and_unidentifiable_binaries(self):
        fetcher, _ = _fetcher(
            [
                FakeResponse(200, b"MZ...", {"Content-Type": "application/x-msdownload"}),
                FakeResponse(200, b"not a pdf", {"Content-Type": "application/octet-stream"}),
            ]
        )
        with self.assertRaisesRegex(FetchError, "Unsupported Content-Type"):
            fetcher.fetch("https://example.gov.in/a")
        with self.assertRaisesRegex(FetchError, "not an identifiable PDF"):
            fetcher.fetch("https://example.gov.in/b")

    def test_non_retryable_status_is_not_retried(self):
        fetcher, session = _fetcher([FakeResponse(403)])
        with self.assertRaisesRegex(FetchError, "HTTP 403") as caught:
            fetcher.fetch("https://example.gov.in/x")
        self.assertFalse(caught.exception.retry_eligible)
        self.assertEqual(len(session.urls), 1)


class ExtractionTests(unittest.TestCase):
    def test_html_keeps_headings_and_drops_navigation(self):
        extracted = extract_html(PAGE)
        self.assertEqual(extracted.title, "Scheme page")
        self.assertIn("# Example Yojana", extracted.text)
        self.assertNotIn("Login", extracted.text)
        self.assertNotIn("Copyright", extracted.text)

    def test_html_falls_back_to_body_when_main_is_an_empty_app_mount(self):
        page = (
            "<html><body><main><div id='root'></div></main><div>"
            + "".join(f"<p>Public copy line {n} about the pension scheme and its benefit.</p>" for n in range(10))
            + "</div></body></html>"
        ).encode()
        self.assertIn("Public copy line 9", extract_html(page).text)

    def test_pdf_text_is_extracted_with_page_markers(self):
        extracted = extract_document(_minimal_pdf("Operational Guidelines 29.03.2020"), "application/pdf")
        self.assertEqual(extracted.page_count, 1)
        self.assertTrue(extracted.text.startswith("[Page 1]"))
        self.assertIn("Operational Guidelines 29.03.2020", extracted.text)

    def test_validation_rejects_a_missing_identity_marker(self):
        with self.assertRaisesRegex(ExtractionError, "markers are missing"):
            validate_extraction(extract_html(PAGE), ["PM-KISAN"])
        metrics = validate_extraction(extract_html(PAGE), ["example yojana"])
        self.assertGreater(metrics["word_count"], 80)

    def test_chunks_repeat_their_page_location(self):
        text = "[Page 1]\n\n" + "\n\n".join(f"Clause {n}. " + "word " * 60 for n in range(8)) + "\n\n[Page 2]\n\nLast clause " + "x " * 60
        chunks = chunk_structured_text(text, target_characters=600)
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(chunk.startswith("[Page ") for chunk in chunks))
        self.assertTrue(chunks[-1].startswith("[Page 2]"))

    def test_text_fingerprint_ignores_only_the_listed_lines(self):
        other_count = PAGE.replace(b"1234", b"98765")
        ignore = ["^Total Visitors: \\d+$"]
        self.assertEqual(_text_pin(PAGE, ignore), _text_pin(other_count, ignore))
        self.assertNotEqual(_text_pin(PAGE), _text_pin(other_count))
        edited = PAGE.replace(b"benefit process", b"benefit procedure")
        self.assertNotEqual(_text_pin(PAGE, ignore), _text_pin(edited, ignore))


class ManifestTests(unittest.TestCase):
    def test_valid_manifest_passes(self):
        cm.validate_manifest(_manifest())

    def test_rejects_run_state_and_unknown_fields(self):
        for field, value in (("snapshot_path", "corpus/staging/x.html"), ("processing_status", "indexed"), ("last_error", None)):
            bad = _manifest(**{field: value})
            with self.subTest(field=field), self.assertRaisesRegex(cm.ManifestError, "unknown field"):
                cm.validate_manifest(bad)

    def test_jurisdiction_must_be_a_migration_0001_code(self):
        for value in ("India", "West Bengal, India", "IN-wb", "WB"):
            with self.subTest(value=value), self.assertRaisesRegex(cm.ManifestError, "jurisdiction"):
                cm.validate_manifest(_manifest(jurisdiction=value))

    def test_source_urls_must_be_https_on_allowlisted_hosts(self):
        with self.assertRaisesRegex(cm.ManifestError, "https"):
            cm.validate_manifest(_manifest(official_url="http://example.gov.in/scheme"))
        with self.assertRaisesRegex(cm.ManifestError, "allowed_hosts"):
            cm.validate_manifest(_manifest(official_url="https://example.com/scheme"))

    def test_service_links_must_be_official(self):
        bad = _manifest()
        bad["items"][0]["official_application_url"] = "https://apply-example.com/"
        with self.assertRaisesRegex(cm.ManifestError, "official"):
            cm.validate_manifest(bad)

    def test_dates_must_be_iso_dates(self):
        with self.assertRaisesRegex(cm.ManifestError, "effective_from"):
            cm.validate_manifest(_manifest(effective_from="1 June 2015"))

    def test_pin_rules(self):
        pin = _manifest()["items"][0]["sources"][0]["pin"]
        cases = {
            "sha256": dict(pin, sha256="ABC"),
            "watch": dict(pin, watch="hash"),
            "text_version": dict(pin, text_version="setu-structured-v0"),
            "ignore_lines": dict(pin, ignore_lines=["("]),
        }
        for message, bad_pin in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(cm.ManifestError, message):
                cm.validate_manifest(_manifest(pin=bad_pin))
        bytes_pin = {"sha256": PAGE_SHA, "retrieved_at": "2026-09-09T06:57:17Z", "watch": "bytes"}
        cm.validate_manifest(_manifest(pin=bytes_pin))
        with self.assertRaisesRegex(cm.ManifestError, "text_sha256"):
            cm.validate_manifest(_manifest(pin=dict(bytes_pin, text_sha256=PAGE_SHA)))

    def test_active_sources_need_a_pin_and_excluded_ones_a_reason(self):
        with self.assertRaisesRegex(cm.ManifestError, "pin"):
            cm.validate_manifest(_manifest(pin=None))
        excluded = _manifest(pin=None)
        excluded["items"][0]["excluded"] = "Official portal served only an app shell"
        cm.validate_manifest(excluded)
        self.assertEqual(list(cm.iter_active_sources(excluded)), [])

    def test_duplicate_ids_and_urls_are_rejected(self):
        manifest = _manifest()
        manifest["items"].append(copy.deepcopy(manifest["items"][0]))
        with self.assertRaisesRegex(cm.ManifestError, "Duplicate"):
            cm.validate_manifest(manifest)


class TrackedManifestTests(unittest.TestCase):
    """The reviewed source lists committed in corpus/manifests."""

    @classmethod
    def setUpClass(cls):
        cls.paths = cm.manifest_paths(MANIFESTS)
        cls.manifests = [cm.load_manifest(path) for path in cls.paths]

    def test_three_batches_with_29_items_load(self):
        self.assertEqual([path.name for path in self.paths], ["batch-001.json", "batch-002.json", "batch-003.json"])
        items = [item for manifest in self.manifests for item in manifest["items"]]
        self.assertEqual(len(items), 29)
        excluded = sorted(item["stable_id"] for item in items if item.get("excluded"))
        self.assertEqual(
            excluded,
            ["scheme.central.mgnrega", "scheme.central.pm-sym", "scheme.wb.lakshmir-bhandar", "scheme.wb.sishu-sathi"],
        )
        active = [source for manifest in self.manifests for _, source in cm.iter_active_sources(manifest)]
        self.assertEqual(len(active), 26)

    def test_ids_and_urls_are_unique_across_batches(self):
        sources = [source for manifest in self.manifests for _, item in enumerate(manifest["items"]) for source in item["sources"]]
        for key in ("source_id", "official_url"):
            values = [source[key] for source in sources]
            self.assertEqual(len(values), len(set(values)), key)

    def test_eshram_faq_pin_is_the_october_review_and_ignores_the_footer_date(self):
        source = next(
            source
            for manifest in self.manifests
            for _, source in cm.iter_active_sources(manifest)
            if source["source_id"] == "eshram.faq.current.en"
        )
        pin = source["pin"]
        self.assertEqual(pin["retrieved_at"][:10], "2026-10-09")
        self.assertEqual(source["updated_date"], "2026-10-09")
        # The site footer restamps "Last Update" daily; a pin that hashed it would fail every week.
        page = "Q - 1. What is eShram?\nLast Update: {}\nTotal Visitors: {}"
        first = text_fingerprint(page.format("09-Oct-2026", 1), pin["ignore_lines"])
        self.assertEqual(first, text_fingerprint(page.format("16-Oct-2026", 2), pin["ignore_lines"]))
        self.assertNotEqual(first, text_fingerprint(page.replace("What", "Why").format("09-Oct-2026", 1), pin["ignore_lines"]))

    def test_west_bengal_pages_are_tagged_in_wb(self):
        for manifest in self.manifests:
            for item, source in cm.iter_active_sources(manifest):
                host = re.sub(r"^https://([^/]+)/.*$", r"\1", source["official_url"])
                expected = "IN-WB" if host.endswith("wb.gov.in") else "IN"
                self.assertEqual(source["jurisdiction"], expected, source["source_id"])
                if item["stable_id"].startswith("scheme.wb."):
                    self.assertEqual(item["jurisdiction"], "IN-WB")

    def test_html_is_watched_by_text_and_pdf_by_bytes(self):
        for manifest in self.manifests:
            for _, source in cm.iter_active_sources(manifest):
                is_pdf = source["official_url"].casefold().endswith(".pdf")
                self.assertEqual(source["pin"]["watch"], "bytes" if is_pdf else "text", source["source_id"])

    def test_no_local_paths_or_run_state_in_tracked_manifests(self):
        for path in self.paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"[A-Za-z]:\\\\|/Users/|/home/|corpus/staging")
            for field in ("processing_status", "snapshot_path", "results", "latency_ms"):
                self.assertNotIn(f'"{field}"', text)


class StateTests(unittest.TestCase):
    def test_stages_only_move_forward_and_state_saves_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            state = corpus_state.RunState.load(Path(directory) / "batch-x" / "state.json", "batch-x")
            record = state.source("a")
            state.advance("a", "fetched")
            state.advance("a", "validated")
            with self.assertRaises(ValueError):
                state.advance("a", "fetched")
            state.save()
            again = corpus_state.RunState.load(Path(directory) / "batch-x" / "state.json", "batch-x")
            self.assertEqual(again.source("a")["stage"], "validated")
            self.assertIs(record, state.source("a"))
            with self.assertRaisesRegex(ValueError, "batch"):
                corpus_state.RunState.load(Path(directory) / "batch-x" / "state.json", "batch-y")


class _Fetched:
    def __init__(self, content, content_type="text/html", final_url=None):
        self.content = content
        self.content_type = content_type
        self.final_url = final_url
        self.status_code = 200
        self.etag = None
        self.last_modified = None


class CollectTests(unittest.TestCase):
    def _run(self, manifest, body):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "batch-test.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        before = path.read_bytes()

        class Fetcher:
            def fetch(self, url):
                return _Fetched(body, final_url=url)

        state = pipeline.collect_batch(path, Path(directory.name) / "staging", fetcher=Fetcher())
        self.assertEqual(path.read_bytes(), before, "collect must never rewrite the reviewed manifest")
        return state, Path(directory.name) / "staging"

    def test_matching_pin_reaches_validated_with_snapshot_in_staging(self):
        state, staging = self._run(_manifest(), PAGE.replace(b"1234", b"55555"))
        record = state.source("example.portal.current")
        self.assertEqual(record["stage"], "validated")
        self.assertTrue(record["pin_matches"])
        self.assertTrue((staging / "batch-test" / "snapshots" / "example.portal.current.html").is_file())
        self.assertRegex(record["content_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(record["retrieved_at"].endswith("Z"))
        self.assertTrue((staging / "batch-test" / "state.json").is_file())

    def test_changed_source_is_held_back_for_a_person(self):
        state, _ = self._run(_manifest(), PAGE.replace(b"benefit process", b"benefit procedure"))
        record = state.source("example.portal.current")
        self.assertEqual(record["stage"], "changed")
        self.assertFalse(record["pin_matches"])
        self.assertIn("re-read", record["last_error"])

    def test_bytes_pin_compares_the_exact_bytes(self):
        pdf = _minimal_pdf("Example Yojana " + "guideline text " * 60)
        pin = {"sha256": hashlib.sha256(pdf).hexdigest(), "retrieved_at": "2026-09-09T06:57:17Z", "watch": "bytes"}
        manifest = _manifest(official_url="https://example.gov.in/guidelines.pdf", pin=pin, min_extracted_characters=200)

        class PdfFetcher:
            def __init__(self, body):
                self.body = body

            def fetch(self, url):
                return _Fetched(self.body, "application/pdf", url)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            ok = pipeline.collect_batch(path, Path(directory) / "s", fetcher=PdfFetcher(pdf))
            self.assertEqual(ok.source("example.portal.current")["stage"], "validated")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            changed = pipeline.collect_batch(path, Path(directory) / "s", fetcher=PdfFetcher(pdf + b"\n"))
            self.assertEqual(changed.source("example.portal.current")["stage"], "changed")

    def test_a_source_failing_validation_is_fetched_again_on_the_next_run(self):
        manifest = _manifest(required_markers=["Operational Guidelines"])

        class Fetcher:
            def fetch(self, url):
                return _Fetched(PAGE, final_url=url)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            for attempt in (1, 2):
                state = pipeline.collect_batch(path, Path(directory) / "s", fetcher=Fetcher())
                record = state.source("example.portal.current")
                self.assertEqual(record["stage"], "extracted")
                self.assertIn("markers are missing", record["last_error"])
                self.assertEqual(record["attempts"], attempt)

    def test_fetch_failure_is_recorded_and_retry_is_possible(self):
        class Failing:
            def fetch(self, url):
                raise FetchError("Official source returned non-retryable HTTP 403")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.json"
            path.write_text(json.dumps(_manifest()), encoding="utf-8")
            state = pipeline.collect_batch(path, Path(directory) / "s", fetcher=Failing())
            record = state.source("example.portal.current")
            self.assertEqual(record["stage"], "discovered")
            self.assertIn("HTTP 403", record["last_error"])
            self.assertEqual(record["attempts"], 1)


class _FakePool:
    async def close(self):
        pass


class IndexTests(unittest.TestCase):
    def test_index_writes_provenance_for_migrations_0001_and_0002(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.json"
            path.write_text(json.dumps(_manifest()), encoding="utf-8")

            class Fetcher:
                def fetch(self, url):
                    return _Fetched(PAGE, final_url=url)

            pipeline.collect_batch(path, Path(directory) / "s", fetcher=Fetcher())
            calls = []

            async def writer(pool, **kwargs):
                calls.append(kwargs)
                return "doc-1"

            def embed(chunks):
                return [[0.0] * 1024 for _ in chunks]

            state = asyncio.run(
                pipeline.index_batch(path, Path(directory) / "s", pool=_FakePool(), embed=embed, writer=writer)
            )
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["jurisdiction"], "IN")
        self.assertEqual(call["effective_from"], date(2015, 6, 1))
        self.assertIsNone(call["effective_to"])
        self.assertEqual(call["source_hash"], PAGE_SHA)
        self.assertIsInstance(call["retrieved_at"], datetime)
        self.assertIsNotNone(call["retrieved_at"].tzinfo)
        self.assertEqual(call["url"], "https://example.gov.in/scheme")
        self.assertEqual(call["metadata"]["corpus_item_id"], "scheme.central.example")
        self.assertEqual(call["metadata"]["official_application_url"], "https://example.gov.in/apply")
        self.assertEqual(call["metadata"]["extraction_version"], EXTRACTION_VERSION)
        self.assertEqual(len(call["chunk_texts"]), len(call["chunk_embeddings"]))
        self.assertEqual(state.source("example.portal.current")["stage"], "indexed")

    def test_changed_or_unvalidated_sources_are_never_indexed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.json"
            path.write_text(json.dumps(_manifest()), encoding="utf-8")

            class Fetcher:
                def fetch(self, url):
                    return _Fetched(PAGE.replace(b"benefit process", b"new text"), final_url=url)

            pipeline.collect_batch(path, Path(directory) / "s", fetcher=Fetcher())

            async def writer(pool, **kwargs):
                raise AssertionError("a changed source must not be written")

            state = asyncio.run(
                pipeline.index_batch(path, Path(directory) / "s", pool=_FakePool(), embed=lambda c: [], writer=writer)
            )
        self.assertEqual(state.source("example.portal.current")["stage"], "changed")

    def test_wrong_embedding_shape_is_a_recorded_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.json"
            path.write_text(json.dumps(_manifest()), encoding="utf-8")

            class Fetcher:
                def fetch(self, url):
                    return _Fetched(PAGE, final_url=url)

            pipeline.collect_batch(path, Path(directory) / "s", fetcher=Fetcher())

            async def writer(pool, **kwargs):
                raise AssertionError("unreachable")

            state = asyncio.run(
                pipeline.index_batch(
                    path, Path(directory) / "s", pool=_FakePool(), embed=lambda c: [[0.0] * 3 for _ in c], writer=writer
                )
            )
        record = state.source("example.portal.current")
        self.assertEqual(record["stage"], "chunked")
        self.assertIn("1024", record["last_error"])


class RetrievalAssessmentTests(unittest.TestCase):
    def test_requires_a_useful_passage_from_the_expected_source(self):
        check = {"expected_rank_max": 2, "expected_passage_markers": ["6,000"]}
        good = [{"url": "https://pmkisan.gov.in/", "content": "Rs 6,000 per year", "rerank_score": 0.9}]
        self.assertTrue(pipeline.assess_retrieval_check(check, good, {"https://pmkisan.gov.in/"})["passed"])
        wrong_passage = [{"url": "https://pmkisan.gov.in/", "content": "Register here", "rerank_score": 0.9}]
        self.assertFalse(pipeline.assess_retrieval_check(check, wrong_passage, {"https://pmkisan.gov.in/"})["passed"])
        wrong_source = [{"url": "https://other.gov.in/", "content": "Rs 6,000", "rerank_score": 0.9}]
        self.assertFalse(pipeline.assess_retrieval_check(check, wrong_source, {"https://pmkisan.gov.in/"})["passed"])

    def test_without_markers_the_expected_source_rank_decides(self):
        check = {"expected_rank_max": 1}
        results = [{"url": "https://pmjdy.gov.in/x", "content": "any"}, {"url": "https://nha.gov.in/y"}]
        self.assertTrue(pipeline.assess_retrieval_check(check, results, {"https://pmjdy.gov.in/x"})["passed"])
        self.assertFalse(pipeline.assess_retrieval_check(check, results, {"https://nha.gov.in/y"})["passed"])

    def test_unsupported_question_passes_only_below_the_score_ceiling(self):
        check = {"expect_no_supported_item": True, "max_top_score": 0.5}
        self.assertTrue(pipeline.assess_retrieval_check(check, [{"rerank_score": 0.2}], set())["passed"])
        self.assertFalse(pipeline.assess_retrieval_check(check, [{"rerank_score": 0.8}], set())["passed"])


class _SchemaConnection:
    def __init__(self, has_init: bool, has_0001: bool, has_0002: bool):
        self.has = {"init": has_init, "0001": has_0001, "0002": has_0002}
        self.executed = []

    async def fetchval(self, sql, *args):
        if "'documents'" in sql and "to_regclass" in sql:
            return self.has["init"]
        if "source_hash" in sql:
            return self.has["0001"]
        if "document_versions" in sql:
            return self.has["0002"]
        raise AssertionError(sql)

    async def execute(self, sql):
        self.executed.append(sql)


class StagingGuardTests(unittest.TestCase):
    def test_only_setu_corpus_staging_names_are_accepted(self):
        for name in ("setu", "postgres", "setu_corpus", "setu_corpus_staging;drop", "SETU_CORPUS_STAGING"):
            with self.subTest(name=name), self.assertRaises(staging_db.StagingDatabaseError):
                staging_db.assert_staging_database_name(name)
        staging_db.assert_staging_database_name("setu_corpus_staging")
        staging_db.assert_staging_database_name("setu_corpus_staging_m2")

    def test_non_loopback_hosts_are_refused(self):
        with self.assertRaises(staging_db.StagingDatabaseError):
            staging_db.LocalDatabaseConfig("u", "p", "10.0.0.8", 5432).assert_loopback()
        with self.assertRaises(staging_db.StagingDatabaseError):
            staging_db.LocalDatabaseConfig("u", "p", "db.example.com", 5432).assert_loopback()
        staging_db.LocalDatabaseConfig("u", "p", "127.0.0.1", 5432).assert_loopback()

    def test_schema_applies_init_then_migrations_once(self):
        # init.sql is not re-runnable (CREATE TRIGGER), and 0001 fails on a second run.
        fresh = _SchemaConnection(False, False, False)
        applied = asyncio.run(staging_db.apply_schema(fresh))
        self.assertEqual(applied, ["init.sql", "0001_jurisdiction_and_effective_dates.up.sql", "0002_document_version_history.up.sql"])
        self.assertEqual(len(fresh.executed), 3)
        done = _SchemaConnection(True, True, True)
        self.assertEqual(asyncio.run(staging_db.apply_schema(done)), [])
        self.assertEqual(done.executed, [])
        half = _SchemaConnection(True, True, False)
        self.assertEqual(asyncio.run(staging_db.apply_schema(half)), ["0002_document_version_history.up.sql"])

    def test_rollback_needs_the_exact_name(self):
        config = staging_db.LocalDatabaseConfig("u", "p", "127.0.0.1", 5432)
        with self.assertRaisesRegex(staging_db.StagingDatabaseError, "confirmation"):
            asyncio.run(staging_db.drop_staging_database(config, "setu_corpus_staging", confirmation="setu"))


if __name__ == "__main__":
    unittest.main()
