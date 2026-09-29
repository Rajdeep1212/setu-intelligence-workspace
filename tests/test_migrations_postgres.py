"""Migrations run against a real PostgreSQL with pgvector.

Skipped unless SETU_TEST_ADMIN_DSN points at a disposable server where the
role may create and drop databases, for example:

    SETU_TEST_ADMIN_DSN=postgresql://postgres@127.0.0.1:55432/postgres \
        python -m unittest tests.test_migrations_postgres -v

Each test creates its own database and drops it afterwards. Ingestion goes
through the real ingestion.db_writer.write_document.
"""

from __future__ import annotations

import asyncio
import os
import unittest
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"
ADMIN_DSN = os.environ.get("SETU_TEST_ADMIN_DSN")
if os.environ.get("SETU_REQUIRE_DB_TESTS") == "1" and not ADMIN_DSN:
    raise RuntimeError("SETU_REQUIRE_DB_TESTS=1 but SETU_TEST_ADMIN_DSN is not set")

HASH_A = "a" * 64
HASH_B = "b" * 64


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def _embedding() -> list[float]:
    return [1.0] + [0.0] * 1023


@unittest.skipUnless(ADMIN_DSN, "set SETU_TEST_ADMIN_DSN to run migrations against PostgreSQL")
class VersionHistoryMigrationTests(unittest.TestCase):
    def setUp(self):
        import asyncpg

        self.asyncpg = asyncpg
        self.database = f"setu_test_{uuid.uuid4().hex[:12]}"
        asyncio.run(self._admin(f'CREATE DATABASE "{self.database}"'))
        base, _, _ = ADMIN_DSN.rpartition("/")
        self.dsn = f"{base}/{self.database}"

    def tearDown(self):
        asyncio.run(self._admin(f'DROP DATABASE IF EXISTS "{self.database}" WITH (FORCE)'))

    async def _admin(self, statement: str) -> None:
        conn = await self.asyncpg.connect(ADMIN_DSN)
        try:
            await conn.execute(statement)
        finally:
            await conn.close()

    def _run(self, coroutine_function):
        async def runner():
            pool = await self.asyncpg.create_pool(self.dsn, min_size=1, max_size=2)
            try:
                return await coroutine_function(pool)
            finally:
                await pool.close()

        return asyncio.run(runner())

    @staticmethod
    async def _apply(pool, *names: str) -> None:
        async with pool.acquire() as conn:
            for name in names:
                try:
                    await conn.execute(_sql(name))
                except Exception:
                    # Like psql -v ON_ERROR_STOP=1: the failed file's transaction is abandoned.
                    await conn.execute("ROLLBACK")
                    raise

    @staticmethod
    async def _write(pool, text: str, source_hash: str | None, url: str = "https://example.gov.in/notice.pdf") -> str:
        from ingestion.db_writer import write_document

        provenance = {}
        if source_hash is not None:
            provenance = {
                "jurisdiction": "IN-WB",
                "effective_from": date(2022, 1, 24),
                "source_hash": source_hash,
                "retrieved_at": datetime.now(timezone.utc),
            }
        return await write_document(
            pool,
            source="test",
            title="Notice",
            language="en",
            url=url,
            raw_text=text,
            metadata={},
            chunk_texts=[text],
            chunk_embeddings=[_embedding()],
            **provenance,
        )

    def test_requires_migration_0001_and_changes_nothing_without_it(self):
        async def scenario(pool):
            await self._apply(pool, "../init.sql")
            with self.assertRaisesRegex(self.asyncpg.RaiseError, "requires migration 0001"):
                await self._apply(pool, "0002_document_version_history.up.sql")
            async with pool.acquire() as conn:
                return await conn.fetchval("SELECT to_regclass('document_versions') IS NULL")

        self.assertTrue(self._run(scenario))

    def test_reingest_keeps_earlier_versions_and_only_the_current_is_retrievable(self):
        async def scenario(pool):
            await self._apply(
                pool,
                "../init.sql",
                "0001_jurisdiction_and_effective_dates.up.sql",
                "0002_document_version_history.up.sql",
            )
            first_id = await self._write(pool, "Helmet: Rs 1,000", HASH_A)
            async with pool.acquire() as conn:
                first_seen = await conn.fetchval("SELECT created_at FROM documents WHERE id = $1", uuid.UUID(first_id))
            await self._write(pool, "Helmet: Rs 1,000", HASH_A)  # unchanged bytes
            unchanged = await self._count(pool)
            second_id = await self._write(pool, "Helmet: Rs 2,000", HASH_B)
            await self._write(pool, "Helmet: Rs 1,000", HASH_A)  # the source changes back
            async with pool.acquire() as conn:
                versions = await conn.fetch(
                    "SELECT raw_text, source_hash, superseded_by_hash, first_seen_at, document_id, jurisdiction "
                    "FROM document_versions ORDER BY superseded_at, id"
                )
                documents = await conn.fetch("SELECT id, raw_text, source_hash FROM documents")
                chunks = await conn.fetch("SELECT content FROM chunks")
            return first_id, second_id, first_seen, unchanged, versions, documents, chunks

        first_id, second_id, first_seen, unchanged, versions, documents, chunks = self._run(scenario)
        self.assertEqual(first_id, second_id)
        self.assertEqual(unchanged, 0)
        self.assertEqual(len(versions), 2)
        self.assertEqual(
            [(v["raw_text"], v["source_hash"], v["superseded_by_hash"]) for v in versions],
            [("Helmet: Rs 1,000", HASH_A, HASH_B), ("Helmet: Rs 2,000", HASH_B, HASH_A)],
        )
        self.assertEqual(versions[0]["first_seen_at"], first_seen)
        self.assertEqual(versions[0]["jurisdiction"], "IN-WB")
        self.assertEqual(str(versions[0]["document_id"]), first_id)
        # Retrieval reads documents and chunks only: one current row per URL.
        self.assertEqual([(d["raw_text"], d["source_hash"]) for d in documents], [("Helmet: Rs 1,000", HASH_A)])
        self.assertEqual([c["content"] for c in chunks], ["Helmet: Rs 1,000"])

    def test_corpus_pipeline_stages_provenance_and_keeps_versions(self):
        """M2.1: staging schema, then two reviewed versions of one scheme page."""
        import hashlib
        import json
        import tempfile

        from ingestion import corpus_pipeline, staging_db
        from tests.test_corpus_pipeline import PAGE, _Fetched, _manifest, _text_pin

        new_page = PAGE.replace(b"benefit process", b"benefit procedure")

        class Fetcher:
            def __init__(self, body):
                self.body = body

            def fetch(self, url):
                return _Fetched(self.body, final_url=url)

        async def scenario(pool):
            async with pool.acquire() as conn:
                applied = await staging_db.apply_schema(conn)
                reapplied = await staging_db.apply_schema(conn)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "batch-test.json"
                stage = Path(directory) / "staging"
                manifest = _manifest()
                path.write_text(json.dumps(manifest), encoding="utf-8")
                corpus_pipeline.collect_batch(path, stage, fetcher=Fetcher(PAGE))
                await corpus_pipeline.index_batch(path, stage, pool=pool, embed=lambda c: [_embedding() for _ in c])
                # A person re-reads the changed page and updates the pin.
                pin = manifest["items"][0]["sources"][0]["pin"]
                pin.update(sha256=hashlib.sha256(new_page).hexdigest(), text_sha256=_text_pin(new_page, pin["ignore_lines"]))
                path.write_text(json.dumps(manifest), encoding="utf-8")
                corpus_pipeline.collect_batch(path, stage, fetcher=Fetcher(new_page))
                state = await corpus_pipeline.index_batch(path, stage, pool=pool, embed=lambda c: [_embedding() for _ in c])
            async with pool.acquire() as conn:
                document = await conn.fetchrow(
                    "SELECT jurisdiction, effective_from, source_hash, retrieved_at, metadata FROM documents"
                )
                chunk_jurisdictions = await conn.fetch("SELECT DISTINCT jurisdiction FROM chunks")
                versions = await conn.fetch("SELECT source_hash, superseded_by_hash FROM document_versions")
            return applied, reapplied, state, document, chunk_jurisdictions, versions

        applied, reapplied, state, document, chunk_jurisdictions, versions = self._run(scenario)
        self.assertEqual(len(applied), 3)
        self.assertEqual(reapplied, [])
        self.assertEqual(state.source("example.portal.current")["stage"], "indexed")
        self.assertEqual(document["jurisdiction"], "IN")
        self.assertEqual(document["effective_from"], date(2015, 6, 1))
        self.assertEqual(document["source_hash"], hashlib.sha256(new_page).hexdigest())
        self.assertIsNotNone(document["retrieved_at"])
        self.assertEqual(json.loads(document["metadata"])["corpus_source_id"], "example.portal.current")
        self.assertEqual([row["jurisdiction"] for row in chunk_jurisdictions], ["IN"])
        self.assertEqual(
            [(v["source_hash"], v["superseded_by_hash"]) for v in versions],
            [(hashlib.sha256(PAGE).hexdigest(), hashlib.sha256(new_page).hexdigest())],
        )

    def test_writer_without_provenance_is_archived_by_text(self):
        async def scenario(pool):
            await self._apply(
                pool,
                "../init.sql",
                "0001_jurisdiction_and_effective_dates.up.sql",
                "0002_document_version_history.up.sql",
            )
            await self._write(pool, "Version one", None)
            await self._write(pool, "Version one", None)
            after_same = await self._count(pool)
            await self._write(pool, "Version two", None)
            return after_same, await self._count(pool)

        self.assertEqual(self._run(scenario), (0, 1))

    def test_second_run_fails_atomically_and_rollback_is_clean(self):
        async def scenario(pool):
            await self._apply(
                pool,
                "../init.sql",
                "0001_jurisdiction_and_effective_dates.up.sql",
                "0002_document_version_history.up.sql",
            )
            await self._write(pool, "Version one", HASH_A)
            await self._write(pool, "Version two", HASH_B)
            with self.assertRaises(self.asyncpg.PostgresError):
                await self._apply(pool, "0002_document_version_history.up.sql")
            still_archived = await self._count(pool)

            await self._apply(pool, "0002_document_version_history.down.sql")
            async with pool.acquire() as conn:
                table_gone = await conn.fetchval("SELECT to_regclass('document_versions') IS NULL")
                trigger_gone = await conn.fetchval(
                    "SELECT count(*) = 0 FROM pg_trigger WHERE tgname = 'documents_archive_version'"
                )
                function_gone = await conn.fetchval(
                    "SELECT count(*) = 0 FROM pg_proc WHERE proname = 'documents_archive_version'"
                )
            await self._write(pool, "Version three", HASH_A)  # ingestion still works
            async with pool.acquire() as conn:
                current = await conn.fetchval("SELECT raw_text FROM documents")

            await self._apply(pool, "0002_document_version_history.up.sql")  # re-apply after rollback
            await self._write(pool, "Version four", HASH_B)
            return still_archived, table_gone, trigger_gone, function_gone, current, await self._count(pool)

        self.assertEqual(self._run(scenario), (1, True, True, True, "Version three", 1))

    def test_deleting_a_document_keeps_its_history(self):
        async def scenario(pool):
            await self._apply(
                pool,
                "../init.sql",
                "0001_jurisdiction_and_effective_dates.up.sql",
                "0002_document_version_history.up.sql",
            )
            await self._write(pool, "Version one", HASH_A)
            await self._write(pool, "Version two", HASH_B)
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM documents")
                return await conn.fetchrow("SELECT document_id, url, raw_text FROM document_versions")

        row = self._run(scenario)
        self.assertIsNone(row["document_id"])
        self.assertEqual((row["url"], row["raw_text"]), ("https://example.gov.in/notice.pdf", "Version one"))

    @staticmethod
    async def _count(pool) -> int:
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT count(*) FROM document_versions")


if __name__ == "__main__":
    unittest.main()
