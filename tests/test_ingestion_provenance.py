"""Phase 1: ingestion writes jurisdiction and effective dates when given.

Offline tests with a fake asyncpg pool. Without provenance values the SQL
must stay byte-identical to the pre-Phase-1 writer, so ingestion keeps
working on a database where migration 0001 has not been applied.
"""

import asyncio
import hashlib
import unittest
from datetime import date

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

        self.assertIn("jurisdiction, effective_from, effective_to", document_sql)
        self.assertIn("jurisdiction = EXCLUDED.jurisdiction", document_sql)
        self.assertIn("ON CONFLICT (url)", document_sql)
        self.assertEqual(document_args[-3:], ("IN-WB", date(2022, 1, 24), None))

        chunk_calls = [(sql, args) for kind, sql, args in calls if kind == "execute" and "INSERT INTO chunks" in sql]
        self.assertEqual(len(chunk_calls), 2)
        for sql, args in chunk_calls:
            self.assertIn("jurisdiction, effective_from, effective_to", sql)
            self.assertEqual(args[-3:], ("IN-WB", date(2022, 1, 24), None))

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
