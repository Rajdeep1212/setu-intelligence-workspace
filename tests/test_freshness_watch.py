"""Phase 4c: the freshness watch compares pinned source hashes.

Offline: a local HTTP server stands in for the government sites, and the
real tables are only read, never fetched.
"""

import contextlib
import hashlib
import io
import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path

from scripts import freshness_watch as watch

BODY = b"%PDF-1.4 notification text"
BODY_SHA = hashlib.sha256(BODY).hexdigest()
IGNORE = ["^Total Visitors: \d+$"]
_visits = iter(range(1000, 10**6))


def _page(visitors: int, clause: str = "benefit process") -> bytes:
    body = "".join(f"<p>Clause {n}: the official {clause} for the scheme.</p>" for n in range(20))
    return f"<html><body><main><h1>Scheme</h1>{body}<p>Total Visitors: {visitors}</p></main></body></html>".encode()


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        if self.path == "/notice.pdf":
            self.send_response(200)
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY)
        elif self.path == "/big.pdf":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x" * 4096)
        elif self.path == "/page.html":
            page = _page(next(_visits))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
        else:
            self.send_response(403)
            self.end_headers()

    def log_message(self, *_args):
        pass


class LocalServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_real_fetcher_hashes_the_served_bytes(self):
        self.assertEqual(watch.fetch_sha256(f"{self.base}/notice.pdf"), BODY_SHA)

    def test_blocked_and_oversized_sources_are_unreachable_not_changed(self):
        with self.assertRaisesRegex(watch.FetchError, "HTTP 403"):
            watch.fetch_sha256(f"{self.base}/blocked.pdf")
        with self.assertRaisesRegex(watch.FetchError, "larger than"):
            watch.fetch_sha256(f"{self.base}/big.pdf", max_bytes=1024)

    def test_altered_pin_fails_and_unchanged_pin_passes(self):
        unchanged = [watch.Source(f"{self.base}/notice.pdf", BODY_SHA, ["WB.json:X"])]
        altered = [watch.Source(f"{self.base}/notice.pdf", "0" * 64, ["WB.json:X"])]
        self.assertEqual(watch.exit_code(watch.check(unchanged)), 0)
        results = watch.check(altered)
        self.assertEqual(results[0].status, "changed")
        self.assertEqual(results[0].current_sha256, BODY_SHA)
        self.assertEqual(watch.exit_code(results), 1)

    def test_text_watch_ignores_a_visitor_counter_but_not_an_edit(self):
        from ingestion.corpus_extract import extract_html, text_fingerprint

        pinned = text_fingerprint(extract_html(_page(1)).text, IGNORE)
        source = watch.Source(f"{self.base}/page.html", pinned, ["batch-x.json:s"], mode="text", ignore_lines=IGNORE)
        self.assertEqual(watch.source_fingerprint(source), pinned)
        self.assertEqual(watch.source_fingerprint(source), pinned)
        self.assertEqual(watch.check([source])[0].status, "unchanged")
        edited = text_fingerprint(extract_html(_page(1, "benefit procedure")).text, IGNORE)
        stale = watch.Source(source.url, edited, source.used_by, mode="text", ignore_lines=IGNORE)
        self.assertEqual(watch.check([stale])[0].status, "changed")
        no_ignore = watch.Source(source.url, pinned, source.used_by, mode="text")
        self.assertEqual(watch.check([no_ignore])[0].status, "changed")


class RuleTests(unittest.TestCase):
    def test_every_pinned_source_in_the_tables_is_loaded_once(self):
        sources = watch.load_sources()
        urls = [source.url for source in sources]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertGreaterEqual(len(sources), 6)
        central = next(s for s in sources if "egazette.gov.in" in s.url)
        self.assertEqual(sorted(central.used_by), ["DL.json:IN-ACT-32-2019", "KA.json:IN-ACT-32-2019", "WB.json:IN-ACT-32-2019"])
        for source in sources:
            self.assertRegex(source.pinned_sha256, r"^[0-9a-f]{64}$")
            self.assertTrue(source.url.startswith("https://"), source.url)

    def test_corpus_manifest_sources_join_the_watch(self):
        sources = watch.load_sources()
        corpus = [s for s in sources if any(u.startswith("batch-") for u in s.used_by)]
        self.assertEqual(len(corpus), 26)
        kisan = next(s for s in corpus if s.url == "https://pmkisan.gov.in/")
        self.assertEqual(kisan.used_by, ["batch-001.json:pm-kisan.portal.current"])
        self.assertEqual(kisan.mode, "text")
        pdf = next(s for s in corpus if s.url.endswith(".pdf"))
        self.assertEqual(pdf.mode, "bytes")
        self.assertFalse(any("nrega.nic.in" in s.url for s in corpus), "excluded sources are not watched")
        traffic = [s for s in sources if s not in corpus]
        self.assertTrue(all(s.mode == "bytes" for s in traffic))

    def test_some_unreachable_passes_but_all_unreachable_fails(self):
        def flaky(url):
            if "a" in url:
                raise watch.FetchError("HTTP 403")
            return "1" * 64

        sources = [watch.Source("https://a.gov.in/x", "1" * 64), watch.Source("https://b.gov.in/y", "1" * 64)]
        self.assertEqual(watch.exit_code(watch.check(sources, flaky)), 0)

        def blocked(_url):
            raise watch.FetchError("connection failed")

        self.assertEqual(watch.exit_code(watch.check(sources, blocked)), 1)
        self.assertIn("No source could be reached", watch.summary_markdown(watch.check(sources, blocked), "now"))

    def test_summary_lists_changed_sources_first_and_asks_for_a_person(self):
        results = [
            watch.Result("https://b.gov.in/ok", "unchanged", "1" * 64, "1" * 64, ["KA.json:K"]),
            watch.Result("https://a.gov.in/new", "changed", "1" * 64, "2" * 64, ["WB.json:W"]),
        ]
        text = watch.summary_markdown(results, "2026-09-28 00:00 UTC")
        table = text.split("|---|---|---|---|\n", 1)[1]
        self.assertTrue(table.startswith("| changed | https://a.gov.in/new"))
        self.assertIn("re-read by a person", text)
        self.assertIn("1 changed, 0 unreachable, 1 unchanged", text)

    def test_cli_writes_summary_and_json_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            report = Path(directory) / "report.json"
            pinned = {source.url: source.pinned_sha256 for source in watch.load_sources()}
            with contextlib.redirect_stdout(io.StringIO()):
                code = watch.main(["--summary", str(summary), "--json-out", str(report)], fetch=pinned.__getitem__)
            self.assertEqual(code, 0)
            self.assertIn("0 changed, 0 unreachable", summary.read_text(encoding="utf-8"))
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual({r["status"] for r in data["results"]}, {"unchanged"})


if __name__ == "__main__":
    unittest.main()
