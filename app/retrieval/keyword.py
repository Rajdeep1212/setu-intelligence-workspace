"""Keyword (full-text) retrieval leg — Week 2."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.filters import RetrievalFilters


async def keyword_search(
    session: AsyncSession,
    query: str,
    language: str | None,
    limit: int,
    *,
    jurisdiction: str | None = None,
    as_of: date | None = None,
) -> list[dict]:
    """
    Postgres full-text search against chunks.tsv (populated by the trigger
    in db/init.sql). Uses the 'simple' text search config — deliberately not
    'english', since it would mangle Hindi/Bengali tokens. 'simple' just
    lowercases and splits on whitespace/punctuation, which is a reasonable
    lowest-common-denominator across all three languages for the keyword leg;
    it's the dense leg that carries most of the semantic weight.

    ``jurisdiction`` and ``as_of`` filter before ranking (see filters.py).
    Without them the statement is unchanged from the pre-Phase-1 query.
    """
    filters = RetrievalFilters(jurisdiction=jurisdiction, as_of=as_of)
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
              AND (CAST(:language AS text) IS NULL OR c.language = CAST(:language AS text)){filter_clause}
            ORDER BY score DESC
            LIMIT :limit
            """.format(filter_clause=filters.sql_clause())
        ),
        {"query": query, "language": language, "limit": limit, **filters.params()},
    )
    return [dict(row._mapping) for row in result]
