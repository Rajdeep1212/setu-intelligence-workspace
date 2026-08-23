from typing import Optional

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    language: Optional[str] = None  # "en" | "hi" | "bn" — auto-detect if omitted


class Citation(BaseModel):
    document_id: str
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    route: Optional[str] = None  # "retrieve_docs" | "check_eligibility" | "summarize"
    confidence: Optional[float] = None
