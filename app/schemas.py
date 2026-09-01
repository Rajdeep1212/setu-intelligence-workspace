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


class EligibilitySummary(BaseModel):
    scheme_name: str
    criteria: dict[str, str | int | float | bool | list[str]]


class SourceSummary(BaseModel):
    id: str
    title: Optional[str] = None
    source: str
    language: Literal["en", "hi", "bn"]
    metadata: dict[str, str] = Field(default_factory=dict)
    chunk_count: int = Field(ge=0)
    eligibility_count: int = Field(ge=0)
    has_eligibility: bool


class SourcesResponse(BaseModel):
    items: list[SourceSummary]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=25)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class SourceDetail(SourceSummary):
    eligibility: list[EligibilitySummary] = Field(default_factory=list)
