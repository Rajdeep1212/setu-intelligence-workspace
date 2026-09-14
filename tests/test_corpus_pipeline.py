from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import requests

from ingestion.corpus_extract import (
    ExtractionError,
    chunk_structured_text,
    extract_html,
    validate_extraction,
)
from ingestion.corpus_manifest import (
    ManifestError,
    advance_stage,
    load_manifest,
    stage_counts,
)
from ingestion.corpus_pipeline import (
    _selected_items,
    assess_retrieval_check,
    verified_link_metadata,
)
from ingestion.safe_fetch import ResponseLimitError, SafeHttpFetcher, UnsafeUrlError
from ingestion.staging_db import StagingDatabaseError, assert_staging_database_name


def public_resolver(host, port, type):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


class FakeResponse:
    def __init__(self, status_code=200, body=b"ok", headers=None):
        self.status_code = status_code
        self.body = body
        self.headers = headers or {"Content-Type": "text/plain"}
        self.closed = False

    def close(self):
        self.closed = True

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield self.body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


class SafeFetcherTests(unittest.TestCase):
    def test_rejects_private_dns_target_even_when_host_is_allowlisted(self):
        fetcher = SafeHttpFetcher(
            ["official.gov.in"],
            resolver=lambda *args, **kwargs: [(2, 1, 6, "", ("169.254.169.254", 443))],
        )
        with self.assertRaisesRegex(UnsafeUrlError, "non-global"):
            fetcher.fetch("https://official.gov.in/document")

    def test_validates_every_redirect_against_exact_allowlist(self):
        session = FakeSession(
            [FakeResponse(302, headers={"Location": "https://evil.example/file.pdf"})]
        )
        fetcher = SafeHttpFetcher(
            ["official.gov.in"], session=session, resolver=public_resolver, retries=0
        )
        with self.assertRaisesRegex(UnsafeUrlError, "exact allowlist"):
            fetcher.fetch("https://official.gov.in/document")
        self.assertTrue(session.responses == [])

    def test_stops_stream_that_exceeds_size_limit(self):
        session = FakeSession(
            [
                FakeResponse(
                    body=b"123456",
                    headers={"Content-Type": "text/plain", "Content-Length": "6"},
                )
            ]
        )
        fetcher = SafeHttpFetcher(
            ["official.gov.in"],
            session=session,
            resolver=public_resolver,
            max_bytes=5,
            retries=0,
        )
        with self.assertRaises(ResponseLimitError):
            fetcher.fetch("https://official.gov.in/document")


class ExtractionTests(unittest.TestCase):
    def test_html_extraction_preserves_headings_and_removes_navigation(self):
        content = b"""
        <html><head><title>Official Scheme</title></head><body>
        <nav>Unrelated menu words repeated forever</nav>
        <main><h1>Scheme Alpha</h1><h2>Eligibility</h2>
        <p>Residents aged eighteen years or older may apply.</p>
        <ul><li>Identity proof is required.</li><li>Residence proof is required.</li></ul>
        <p>This official explanation contains enough additional words to represent
        a useful public-information source passage for the extraction validator.
        It explains the application route, the responsible public department,
        the review process, the source date, the available benefit, exceptions,
        and the supporting evidence an applicant should retain. The wording here
        is deliberately repetitive enough for a realistic minimum quality gate,
        while the assertions remain fixtures rather than real scheme facts.</p>
        </main></body></html>
        """
        extracted = extract_html(content)
        self.assertEqual(extracted.title, "Official Scheme")
        self.assertIn("# Scheme Alpha", extracted.text)
        self.assertIn("## Eligibility", extracted.text)
        self.assertNotIn("Unrelated menu", extracted.text)
        metrics = validate_extraction(
            extracted, ["Scheme Alpha", "Residence proof"], min_characters=100
        )
        self.assertGreater(metrics["word_count"], 20)

    def test_validation_rejects_missing_identity_marker(self):
        extracted = extract_html(b"<main><p>" + b"ordinary text " * 100 + b"</p></main>")
        with self.assertRaisesRegex(ExtractionError, "Required source markers"):
            validate_extraction(extracted, ["Act No. 99 of 2099"])

    def test_html_extraction_falls_back_when_main_is_an_empty_app_mount(self):
        content = b"""
        <html><head><title>Official Portal</title></head><body>
        <main id="app"></main>
        <section><h1>Scheme Alpha</h1>
        <p>The official public information is rendered outside the empty app
        mount and must remain available to the bounded corpus extractor.</p>
        </section></body></html>
        """
        extracted = extract_html(content)
        self.assertIn("# Scheme Alpha", extracted.text)
        self.assertIn("official public information", extracted.text)

    def test_html_extraction_preserves_content_inside_aspnet_form_wrapper(self):
        content = b"""
        <html><body><form method="post">
        <input type="hidden" value="opaque state" />
        <h1>Scheme Alpha</h1><p>Official scheme details remain readable even
        when an ASP.NET page wraps its whole body in a form element.</p>
        <button>Submit</button>
        </form></body></html>
        """
        extracted = extract_html(content)
        self.assertIn("# Scheme Alpha", extracted.text)
        self.assertIn("Official scheme details", extracted.text)
        self.assertNotIn("Submit", extracted.text)

    def test_chunking_repeats_page_location(self):
        text = "[Page 7]\n\n" + ("A public entitlement sentence. " * 120)
        chunks = chunk_structured_text(text, target_characters=500)
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(chunk.startswith("[Page 7]") for chunk in chunks))


class ManifestTests(unittest.TestCase):
    def test_non_web_official_service_link_is_rejected(self):
        manifest = json.loads(
            (Path("corpus/manifests/batch-001.json")).read_text(encoding="utf-8")
        )
        manifest["items"][0]["official_application_url"] = "javascript:alert(1)"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_manifest(path)

    def _manifest(self):
        return {
            "schema_version": 1,
            "batch_id": "batch-test",
            "fetch_policy": {"allowed_hosts": ["official.gov.in"]},
            "items": [
                {
                    "stable_id": "scheme.central.alpha",
                    "canonical_title": "Alpha",
                    "item_type": "central_scheme",
                    "jurisdiction": "India",
                    "publisher": "Government",
                    "processing_status": "discovered",
                    "sources": [
                        {
                            "source_id": "alpha.page.en",
                            "document_title": "Alpha page",
                            "source_type": "official_page",
                            "official_url": "https://official.gov.in/alpha",
                            "language": "en",
                            "coverage_scope": "Scheme overview",
                            "required_markers": ["Alpha"],
                            "processing_status": "discovered",
                            "attempt_count": 0,
                        }
                    ],
                    "retrieval_checks": [{"check_id": "alpha.q1", "query": "Alpha?"}],
                }
            ],
        }

    def test_load_and_cumulative_stage_counts(self):
        manifest = self._manifest()
        advance_stage(manifest["items"][0]["sources"][0], "validated")
        manifest["items"][0]["processing_status"] = "validated"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = load_manifest(path)
        counts = stage_counts(loaded)
        self.assertEqual(counts["discovered"], 1)
        self.assertEqual(counts["validated"], 1)
        self.assertEqual(counts["deduplicated"], 0)

    def test_duplicate_source_url_is_rejected(self):
        manifest = self._manifest()
        duplicate = json.loads(json.dumps(manifest["items"][0]))
        duplicate["stable_id"] = "scheme.central.beta"
        duplicate["sources"][0]["source_id"] = "beta.page.en"
        manifest["items"].append(duplicate)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "Duplicate source URL"):
                load_manifest(path)

    def test_non_text_passage_marker_is_rejected(self):
        manifest = self._manifest()
        manifest["items"][0]["retrieval_checks"][0][
            "expected_passage_markers"
        ] = [123]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "expected_passage_markers"):
                load_manifest(path)


class RetrievalAssessmentTests(unittest.TestCase):
    def test_verified_link_metadata_omits_missing_or_unverified_values(self):
        self.assertEqual(
            verified_link_metadata(
                {
                    "official_application_url": "https://apply.example.gov.in/",
                    "official_status_url": None,
                    "official_help_url": "",
                }
            ),
            {"official_application_url": "https://apply.example.gov.in/"},
        )

    def test_requires_useful_passage_marker_in_expected_source(self):
        check = {
            "expected_rank_max": 2,
            "expected_passage_markers": ["local Gram Panchayat"],
        }
        result = assess_retrieval_check(
            check,
            [
                {
                    "url": "https://official.gov.in/mgnrega",
                    "content": "Apply on plain paper to the local Gram Panchayat.",
                    "rerank_score": 0.9,
                }
            ],
            {"https://official.gov.in/mgnrega"},
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["passage_passed"])

    def test_correct_document_without_useful_passage_fails(self):
        check = {
            "expected_rank_max": 2,
            "expected_passage_markers": ["local Gram Panchayat"],
        }
        result = assess_retrieval_check(
            check,
            [
                {
                    "url": "https://official.gov.in/mgnrega",
                    "content": "A generic programme overview.",
                    "rerank_score": 0.9,
                }
            ],
            {"https://official.gov.in/mgnrega"},
        )
        self.assertFalse(result["passed"])

    def test_default_selection_skips_quarantined_items(self):
        manifest = {
            "items": [
                {"stable_id": "scheme.central.good", "processing_status": "validated"},
                {"stable_id": "scheme.central.bad", "processing_status": "excluded"},
            ]
        }
        self.assertEqual(
            [item["stable_id"] for item in _selected_items(manifest, None)],
            ["scheme.central.good"],
        )


class StagingGuardTests(unittest.TestCase):
    def test_application_database_name_is_never_a_staging_target(self):
        with self.assertRaises(StagingDatabaseError):
            assert_staging_database_name("setu")
        assert_staging_database_name("setu_corpus_staging")
        assert_staging_database_name("setu_corpus_staging_batch_001")


if __name__ == "__main__":
    unittest.main()
