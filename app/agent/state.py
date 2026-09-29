"""Shared state passed between LangGraph nodes — Week 3."""

from __future__ import annotations

from datetime import date
from typing import Optional, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    language: Optional[str]
    jurisdiction: Optional[str]
    as_of: Optional[date]
    route: str
    scheme_name_hint: Optional[str]
    retrieved_chunks: list[dict]
    eligibility_matches: list[dict]
    answer: str
    citations: list[dict]
    sections: list[dict]
    response_status: str
    confidence: Optional[float]
    premise_check: Optional[dict]
    scam_check: Optional[dict]
