"""
DB writer — Week 1.

Standalone asyncpg writer (deliberately not the app's SQLAlchemy session —
ingestion runs as an offline script/cron job, not inside a request, and
asyncpg's `copy_records_to_table` is much faster than row-by-row ORM
inserts for bulk loads like this).
"""

from __future__ import annotations

import json
import os
import re
from datetime import date

import asyncpg

DATABASE_DSN = os.environ.get(
    "INGEST_DATABASE_DSN",
    "postgresql://setu:setu@localhost:5432/setu",  # local Docker Compose default
)

# Mirrors the check constraint in db/migrations/0001_jurisdiction_and_effective_dates.up.sql.
_JURISDICTION_PATTERN = re.compile(r"^IN(-[A-Z]{2})?$")


def _validate_provenance(
    jurisdiction: str | None, effective_from: date | None, effective_to: date | None
) -> None:
    if jurisdiction is not None and not _JURISDICTION_PATTERN.fullmatch(jurisdiction):
        raise ValueError("jurisdiction must be 'IN' or 'IN-' followed by two capital letters")
    for name, value in (("effective_from", effective_from), ("effective_to", effective_to)):
        if value is not None and not isinstance(value, date):
            raise ValueError(f"{name} must be a date")
    if effective_from is not None and effective_to is not None and effective_to <= effective_from:
        raise ValueError("effective_to must be after effective_from (the range is half-open)")


async def write_document(
    pool: asyncpg.Pool,
    *,
    source: str,
    title: str,
    language: str,
    url: str,
    raw_text: str,
    metadata: dict,
    chunk_texts: list[str],
    chunk_embeddings: list[list[float]],
    jurisdiction: str | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> str:
    """
    Insert one document row, then one row per chunk (with its embedding).
    Returns the new document's id.

    ``jurisdiction``, ``effective_from`` and ``effective_to`` (Phase 1) are
    written to the document and copied to each chunk. They need migration
    0001. When all three are None the statements are unchanged, so ingestion
    still works on a database where that migration has not been applied.
    """
    assert len(chunk_texts) == len(chunk_embeddings), "chunk/embedding count mismatch"
    _validate_provenance(jurisdiction, effective_from, effective_to)
    with_provenance = any(
        value is not None for value in (jurisdiction, effective_from, effective_to)
    )

    async with pool.acquire() as conn:
        async with conn.transaction():
            if with_provenance:
                document_id = await conn.fetchval(
                    """
                    INSERT INTO documents (
                        source, title, language, url, raw_text, metadata,
                        jurisdiction, effective_from, effective_to
                    )
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        raw_text = EXCLUDED.raw_text,
                        metadata = EXCLUDED.metadata,
                        jurisdiction = EXCLUDED.jurisdiction,
                        effective_from = EXCLUDED.effective_from,
                        effective_to = EXCLUDED.effective_to,
                        created_at = now()
                    RETURNING id
                    """,
                    source,
                    title,
                    language,
                    url,
                    raw_text,
                    json.dumps(metadata),
                    jurisdiction,
                    effective_from,
                    effective_to,
                )
            else:
                document_id = await conn.fetchval(
                    """
                INSERT INTO documents (source, title, language, url, raw_text, metadata)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    raw_text = EXCLUDED.raw_text,
                    metadata = EXCLUDED.metadata,
                    created_at = now()
                RETURNING id
                """,
                    source,
                    title,
                    language,
                    url,
                    raw_text,
                    json.dumps(metadata),
                )

            # Clear any existing chunks for this document if it was an update
            await conn.execute("DELETE FROM chunks WHERE document_id = $1", document_id)

            for idx, (chunk, embedding) in enumerate(zip(chunk_texts, chunk_embeddings)):
                # pgvector accepts a string literal like '[0.1,0.2,...]'
                embedding_literal = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
                if with_provenance:
                    await conn.execute(
                        """
                        INSERT INTO chunks (
                            document_id, chunk_index, language, content, embedding,
                            jurisdiction, effective_from, effective_to
                        )
                        VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $8)
                        """,
                        document_id,
                        idx,
                        language,
                        chunk,
                        embedding_literal,
                        jurisdiction,
                        effective_from,
                        effective_to,
                    )
                else:
                    await conn.execute(
                        """
                    INSERT INTO chunks (document_id, chunk_index, language, content, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    """,
                        document_id,
                        idx,
                        language,
                        chunk,
                        embedding_literal,
                    )

    return str(document_id)


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DATABASE_DSN, min_size=1, max_size=5)
