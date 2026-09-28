"""Dense retrieval leg — Week 2."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.filters import RetrievalFilters


def _to_vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


async def dense_search(
    session: AsyncSession,
    query_vector: list[float],
    language: str | None,
    limit: int,
    *,
    jurisdiction: str | None = None,
    as_of: date | None = None,
) -> list[dict]:
    """
    Cosine similarity search over chunks.embedding using pgvector's `<=>`
    operator (cosine distance — smaller is more similar). We convert to a
    similarity score (1 - distance) so higher is always "more relevant"
    across both retrieval legs, which fusion.py relies on.

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
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE (CAST(:language AS text) IS NULL OR c.language = CAST(:language AS text)){filter_clause}
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """.format(filter_clause=filters.sql_clause())
        ),
        {
            "embedding": _to_vector_literal(query_vector),
            "language": language,
            "limit": limit,
            **filters.params(),
        },
    )
    return [dict(row._mapping) for row in result]
