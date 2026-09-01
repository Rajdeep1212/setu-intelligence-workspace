"""Keyword (full-text) retrieval leg — Week 2."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def keyword_search(
    session: AsyncSession,
    query: str,
    language: str | None,
    limit: int,
) -> list[dict]:
    """
    Postgres full-text search against chunks.tsv (populated by the trigger
    in db/init.sql). Uses the 'simple' text search config — deliberately not
    'english', since it would mangle Hindi/Bengali tokens. 'simple' just
    lowercases and splits on whitespace/punctuation, which is a reasonable
    lowest-common-denominator across all three languages for the keyword leg;
    it's the dense leg that carries most of the semantic weight.
    """
    result = await session.execute(
        text(
            """
            SELECT
                c.id::text AS id,
                c.document_id::text AS document_id,
                c.content,
                c.language,
                d.title,
                d.source,
                d.url,
                ts_rank(c.tsv, plainto_tsquery('simple', :query)) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.tsv @@ plainto_tsquery('simple', :query)
              AND (CAST(:language AS text) IS NULL OR c.language = CAST(:language AS text))
            ORDER BY score DESC
            LIMIT :limit
            """
        ),
        {"query": query, "language": language, "limit": limit},
    )
    return [dict(row._mapping) for row in result]
