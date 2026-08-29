"""Structured-output schemas for the agent — Week 3."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal["retrieve_docs", "check_eligibility"] = Field(
        description=(
            "'check_eligibility' only when the user is asking whether they "
            "personally qualify for one specific named scheme (income/age/"
            "state limits etc). 'retrieve_docs' for everything else — "
            "general questions, 'what is X', 'how do I apply', comparisons."
        )
    )
    scheme_name_hint: Optional[str] = Field(
        default=None,
        description=(
            "If route is check_eligibility, the scheme name as best guessed "
            "from the query, e.g. 'PM Kisan'. Otherwise omit."
        ),
    )


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(
        description=(
            "A grounded answer based ONLY on the provided context, in the "
            "same language as the question. If the context doesn't answer "
            "the question, say so plainly instead of guessing."
        )
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Self-assessed confidence that the context actually answers the question.",
    )
    citation_ids: list[str] = Field(
        max_length=5,
        description=(
            "Chunk IDs from the provided context that materially support the "
            "answer. Never invent an ID and omit chunks that were not used."
        ),
    )
    abstained: bool = Field(
        description=(
            "True when the supplied evidence is insufficient for a grounded answer."
        ),
    )
