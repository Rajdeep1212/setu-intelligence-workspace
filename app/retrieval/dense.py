"""Dense retrieval leg — Week 2."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _to_vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


async def dense_search(
    session: AsyncSession,
    query_vector: list[float],
    language: str | None,
    limit: int,
) -> list[dict]:
    """
    Cosine similarity search over chunks.embedding using pgvector's `<=>`
    operator (cosine distance — smaller is more similar). We convert to a
    similarity score (1 - distance) so higher is always "more relevant"
    across both retrieval legs, which fusion.py relies on.
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
                d.url,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE (:language IS NULL OR c.language = :language)
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        ),
        {
            "embedding": _to_vector_literal(query_vector),
            "language": language,
            "limit": limit,
        },
    )
    return [dict(row._mapping) for row in result]
