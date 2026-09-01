"""Bounded, read-only source catalogue queries."""

from __future__ import annotations

import math
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import DatabaseUnavailableError, SourceNotFoundError
from app.schemas import (
    EligibilitySummary,
    SourceDetail,
    SourceSummary,
    SourcesResponse,
)


LIST_SQL = text(
    """
    WITH filtered AS (
      SELECT d.id, d.title, d.source, d.language, d.metadata
      FROM documents d
      WHERE (CAST(:language AS text) IS NULL OR d.language = CAST(:language AS text))
        AND (
          CAST(:search AS text) IS NULL
          OR lower(coalesce(d.title, '')) LIKE CAST(:search AS text) ESCAPE '\\'
          OR lower(d.source) LIKE CAST(:search AS text) ESCAPE '\\'
        )
        AND (
          CAST(:has_eligibility AS boolean) IS NULL
          OR EXISTS (
            SELECT 1 FROM eligibility_criteria ec
            WHERE ec.source_document_id = d.id
          ) = CAST(:has_eligibility AS boolean)
        )
    )
    SELECT f.id, f.title, f.source, f.language, f.metadata,
           count(DISTINCT c.id)::int AS chunk_count,
           count(DISTINCT ec.id)::int AS eligibility_count
    FROM filtered f
    LEFT JOIN chunks c ON c.document_id = f.id
    LEFT JOIN eligibility_criteria ec ON ec.source_document_id = f.id
    GROUP BY f.id, f.title, f.source, f.language, f.metadata
    ORDER BY coalesce(f.title, ''), f.id
    LIMIT :limit OFFSET :offset
    """
)

COUNT_SQL = text(
    """
    SELECT count(*)::int
    FROM documents d
    WHERE (CAST(:language AS text) IS NULL OR d.language = CAST(:language AS text))
      AND (
        CAST(:search AS text) IS NULL
        OR lower(coalesce(d.title, '')) LIKE CAST(:search AS text) ESCAPE '\\'
        OR lower(d.source) LIKE CAST(:search AS text) ESCAPE '\\'
      )
      AND (
        CAST(:has_eligibility AS boolean) IS NULL
        OR EXISTS (
          SELECT 1 FROM eligibility_criteria ec
          WHERE ec.source_document_id = d.id
        ) = CAST(:has_eligibility AS boolean)
      )
    """
)

DETAIL_SQL = text(
    """
    SELECT d.id, d.title, d.source, d.language, d.metadata,
           count(DISTINCT c.id)::int AS chunk_count,
           count(DISTINCT ec.id)::int AS eligibility_count
    FROM documents d
    LEFT JOIN chunks c ON c.document_id = d.id
    LEFT JOIN eligibility_criteria ec ON ec.source_document_id = d.id
    WHERE d.id = :source_id
    GROUP BY d.id, d.title, d.source, d.language, d.metadata
    """
)

ELIGIBILITY_SQL = text(
    """
    SELECT scheme_name, criteria
    FROM eligibility_criteria
    WHERE source_document_id = :source_id
    ORDER BY scheme_name
    LIMIT 10
    """
)

SAFE_METADATA_KEYS = frozenset({"posted_on", "prid"})
SAFE_CRITERIA_KEYS = frozenset(
    {
        "benefit",
        "description",
        "max_family_income",
        "eligible_categories",
        "max_landholding",
        "excluded_categories",
        "min_age",
        "documents_required",
    }
)


def _escape_search(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    escaped = value.strip().lower().replace("\\", "\\\\")
    escaped = escaped.replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _safe_mapping(value: object, allowed: frozenset[str]) -> dict:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if key in allowed
        and isinstance(item, (str, int, float, bool, list))
        and not isinstance(item, dict)
    }


def _summary(row) -> SourceSummary:
    eligibility_count = int(row["eligibility_count"] or 0)
    metadata = _safe_mapping(row["metadata"], SAFE_METADATA_KEYS)
    return SourceSummary(
        id=str(row["id"]),
        title=row["title"],
        source=row["source"],
        language=row["language"],
        metadata={key: str(value) for key, value in metadata.items()},
        chunk_count=int(row["chunk_count"] or 0),
        eligibility_count=eligibility_count,
        has_eligibility=eligibility_count > 0,
    )


async def list_sources(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None,
    language: Literal["en", "hi", "bn"] | None,
    has_eligibility: bool | None,
) -> SourcesResponse:
    parameters = {
        "language": language,
        "search": _escape_search(search),
        "has_eligibility": has_eligibility,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    try:
        total = int((await session.execute(COUNT_SQL, parameters)).scalar_one())
        rows = (await session.execute(LIST_SQL, parameters)).mappings().all()
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError() from exc
    return SourcesResponse(
        items=[_summary(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


async def get_source(session: AsyncSession, source_id: UUID) -> SourceDetail:
    parameters = {"source_id": source_id}
    try:
        row = (await session.execute(DETAIL_SQL, parameters)).mappings().one_or_none()
        if row is None:
            raise SourceNotFoundError()
        eligibility_rows = (
            (await session.execute(ELIGIBILITY_SQL, parameters)).mappings().all()
        )
    except SourceNotFoundError:
        raise
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError() from exc
    summary = _summary(row)
    return SourceDetail(
        **summary.model_dump(),
        eligibility=[
            EligibilitySummary(
                scheme_name=item["scheme_name"],
                criteria=_safe_mapping(item["criteria"], SAFE_CRITERIA_KEYS),
            )
            for item in eligibility_rows
        ],
    )
