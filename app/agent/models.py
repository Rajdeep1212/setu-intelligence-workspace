"""Structured-output schemas for the agent — Week 3."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class GeneratedClaim(BaseModel):
    """One provider-authored answer section and its claimed evidence IDs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1)
    citation_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("citation_ids")
    @classmethod
    def reject_duplicate_citations(cls, value: list[str]) -> list[str]:
        if any(not citation_id.strip() for citation_id in value):
            raise ValueError("claim citation IDs must not be blank")
        if len(value) != len(set(value)):
            raise ValueError("claim citation IDs must be unique")
        return value


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(
        description=(
            "An evidence-constrained answer based ONLY on the provided context, in the "
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
    claims: list[GeneratedClaim] = Field(
        default_factory=list,
        max_length=12,
        description=(
            "Claim-specific answer sections. Each citation ID must come from "
            "the supplied context. Older provider responses may omit this "
            "field and use answer plus citation_ids as one whole-answer section."
        ),
    )
    abstained: bool = Field(
        description=(
            "True when the supplied evidence is insufficient for an answer."
        ),
    )
