"""Agent tools — Week 3."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import DatabaseUnavailableError
from app.retrieval.pipeline import retrieve


async def retrieve_docs_tool(
    session: AsyncSession, query: str, language: str | None
) -> list[dict]:
    return await retrieve(session, query, language=language)


async def check_eligibility_tool(session: AsyncSession, scheme_name_hint: str) -> list[dict]:
    """
    Naive ILIKE lookup against eligibility_criteria.scheme_name — good
    enough for the handful of hand-entered schemes from
    `ingestion/seed_eligibility.py`. Swap for a proper fuzzy/embedding
    search once this table grows past a few dozen schemes.
    """
    try:
        result = await session.execute(
            text(
                """
            SELECT
                id::text AS id,
                scheme_name,
                criteria,
                source_document_id::text AS source_document_id
            FROM eligibility_criteria
            WHERE scheme_name ILIKE :pattern
            LIMIT 5
            """
            ),
            {"pattern": f"%{scheme_name_hint}%"},
        )
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError() from exc
    return [dict(row._mapping) for row in result]
