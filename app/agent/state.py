"""Shared state passed between LangGraph nodes — Week 3."""

from __future__ import annotations

from typing import Optional, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    language: Optional[str]
    route: str
    scheme_name_hint: Optional[str]
    retrieval_query: str
    retrieval_retry_count: int
    retrieved_chunks: list[dict]
    eligibility_matches: list[dict]
    answer: str
    citations: list[dict]
    sections: list[dict]
    official_links: list[dict]
    clarification_message: Optional[str]
    response_status: str
    confidence: Optional[float]
