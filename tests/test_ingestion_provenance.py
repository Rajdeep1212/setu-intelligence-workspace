"""Phase 1: ingestion writes jurisdiction and effective dates when given.

Offline tests with a fake asyncpg pool. Without provenance values the SQL
must stay byte-identical to the pre-Phase-1 writer, so ingestion keeps
working on a database where migration 0001 has not been applied.
"""

import asyncio
import hashlib
import unittest
from datetime import date, datetime, timezone

from ingestion import db_writer

UNFILTERED_DOCUMENT_SQL_SHA256 = "79c628de6222117b23cdaac8d48510205c411226392bb02f5103a55156440c2d"
UNFILTERED_CHUNK_SQL_SHA256 = "55a0c40799912d0d4a3be4a8ad2ca6d8145a78c61d33e0492e6e0983040177ef"


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Connection:
    def __init__(self):
        self.calls = []

    def transaction(self):
        return _Transaction()

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        return "document-1"

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *exc):
        return False


class _Pool:
    def __init__(self):
        self.connection = _Connection()

    def acquire(self):
        return _Acquire(self.connection)


def _write(**provenance):
    pool = _Pool()
    asyncio.run(
        db_writer.write_document(
            pool,
            source="PIB",
            title="Title",
            language="en",
            url="https://example.gov.in/release",
            raw_text="Body",
            metadata={"prid": "1"},
            chunk_texts=["first", "second"],
            chunk_embeddings=[[0.1], [0.2]],
            **provenance,
        )
    )
    return pool.connection.calls


def _sha(sql):
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


class IngestionProvenanceTests(unittest.TestCase):
    def test_without_provenance_sql_is_unchanged(self):
        calls = _write()
        document_sql = calls[0][1]
        chunk_sqls = [sql for kind, sql, _ in calls if kind == "execute" and "INSERT INTO chunks" in sql]

        self.assertEqual(_sha(document_sql), UNFILTERED_DOCUMENT_SQL_SHA256)
        self.assertEqual(len(chunk_sqls), 2)
        for sql in chunk_sqls:
            self.assertEqual(_sha(sql), UNFILTERED_CHUNK_SQL_SHA256)
        for _, sql, _ in calls:
            self.assertNotIn("jurisdiction", sql)

    def test_with_provenance_document_and_chunks_carry_values(self):
        calls = _write(jurisdiction="IN-WB", effective_from=date(2022, 1, 24))
        _, document_sql, document_args = calls[0]

        self.assertIn("jurisdiction, effective_from, effective_to, source_hash, retrieved_at", document_sql)
        self.assertIn("jurisdiction = EXCLUDED.jurisdiction", document_sql)
        self.assertIn("source_hash = EXCLUDED.source_hash", document_sql)
        self.assertIn("ON CONFLICT (url)", document_sql)
        self.assertEqual(document_args[-5:], ("IN-WB", date(2022, 1, 24), None, None, None))

        chunk_calls = [(sql, args) for kind, sql, args in calls if kind == "execute" and "INSERT INTO chunks" in sql]
        self.assertEqual(len(chunk_calls), 2)
        for sql, args in chunk_calls:
            self.assertIn("jurisdiction, effective_from, effective_to, source_hash, retrieved_at", sql)
            self.assertEqual(args[-5:], ("IN-WB", date(2022, 1, 24), None, None, None))

    def test_source_hash_and_retrieval_time_are_written_to_document_and_chunks(self):
        fetched = datetime(2026, 9, 28, 4, 30, tzinfo=timezone.utc)
        digest = "a" * 64
        calls = _write(source_hash=digest, retrieved_at=fetched)
        for kind, sql, args in calls:
            if "INSERT INTO" in sql:
                self.assertEqual(args[-2:], (digest, fetched), kind)

    def test_values_are_bound_not_formatted(self):
        for _, sql, _ in _write(jurisdiction="IN-KA", effective_to=date(2030, 1, 1)):
            self.assertNotIn("IN-KA", sql)
            self.assertNotIn("2030", sql)

    def test_invalid_provenance_is_rejected_before_writing(self):
        for provenance in (
            {"jurisdiction": "IN-WB-KOL"},
            {"jurisdiction": "wb"},
            {"effective_from": "2022-01-24"},
            {"effective_from": date(2022, 1, 24), "effective_to": date(2022, 1, 24)},
            {"effective_from": date(2022, 1, 24), "effective_to": date(2021, 1, 1)},
            {"effective_from": datetime(2022, 1, 24, tzinfo=timezone.utc)},
            {"source_hash": "ABC"},
            {"source_hash": "A" * 64},
            {"retrieved_at": "2026-09-28"},
            {"retrieved_at": datetime(2026, 9, 28)},
        ):
            pool = _Pool()
            with self.subTest(provenance=provenance), self.assertRaises(ValueError):
                asyncio.run(
                    db_writer.write_document(
                        pool,
                        source="PIB",
                        title="Title",
                        language="en",
                        url="https://example.gov.in/release",
                        raw_text="Body",
                        metadata={},
                        chunk_texts=["first"],
                        chunk_embeddings=[[0.1]],
                        **provenance,
                    )
                )
            self.assertEqual(pool.connection.calls, [])


if __name__ == "__main__":
    unittest.main()


class ProvenanceDetectionTests(unittest.TestCase):
    def test_detects_migration_from_column_count(self):
        class Conn:
            def __init__(self, count):
                self.count = count

            async def fetchval(self, sql, columns):
                self.columns = columns
                return self.count

        for count, expected in ((10, True), (0, False), (6, False)):
            pool = _Pool()
            pool.connection = Conn(count)
            with self.subTest(count=count):
                self.assertIs(asyncio.run(db_writer.has_provenance_columns(pool)), expected)
                self.assertEqual(sorted(pool.connection.columns), sorted(db_writer.PROVENANCE_COLUMNS))


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_is_sha256_of_exact_bytes(self):
        from ingestion.provenance import source_fingerprint

        self.assertEqual(source_fingerprint(b"abc"), hashlib.sha256(b"abc").hexdigest())
        self.assertNotEqual(source_fingerprint(b"abc"), source_fingerprint(b"abc "))
        with self.assertRaises(TypeError):
            source_fingerprint("abc")

    def test_retrieval_time_is_utc(self):
        from ingestion.provenance import retrieved_now

        self.assertEqual(retrieved_now().utcoffset().total_seconds(), 0)


def _scraper_available() -> bool:
    import importlib.util

    return all(importlib.util.find_spec(name) for name in ("bs4", "requests", "lxml"))


@unittest.skipUnless(_scraper_available(), "scraper dependencies (requirements-ingestion.txt) not installed")
class ScraperProvenanceTests(unittest.TestCase):
    def test_fetch_records_hash_of_exact_bytes_and_utc_time(self):
        from unittest.mock import patch

        from ingestion import scraper

        body = (
            "<html><head><meta property='og:title' content='Release'></head><body>"
            "<div class='innner-page-main-about-us-content-right-part'>" + ("Road safety text. " * 30)
            + "</div></body></html>"
        ).encode("utf-8")

        class Response:
            content = body
            text = body.decode("utf-8")

            def raise_for_status(self):
                return None

        with patch.object(scraper.requests, "get", return_value=Response()):
            document = scraper.fetch_release("123")

        self.assertEqual(document.source_hash, hashlib.sha256(body).hexdigest())
        self.assertIsNotNone(document.retrieved_at.tzinfo)
        self.assertEqual(document.retrieved_at.utcoffset().total_seconds(), 0)
