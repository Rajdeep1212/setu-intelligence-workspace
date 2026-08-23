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

import asyncpg

DATABASE_DSN = os.environ.get(
    "INGEST_DATABASE_DSN",
    "postgresql://setu:setu@localhost:5432/setu",  # local Docker Compose default
)


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
) -> str:
    """
    Insert one document row, then one row per chunk (with its embedding).
    Returns the new document's id.
    """
    assert len(chunk_texts) == len(chunk_embeddings), "chunk/embedding count mismatch"

    async with pool.acquire() as conn:
        async with conn.transaction():
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
