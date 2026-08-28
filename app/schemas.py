from typing import Literal, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    language: Optional[Literal["en", "hi", "bn"]] = None


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    route: Optional[str] = None
    confidence: Optional[float] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
