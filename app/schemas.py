from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    language: Optional[Literal["en", "hi", "bn"]] = None

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    title: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None


class AnswerSection(BaseModel):
    text: str = Field(min_length=1)
    kind: Optional[
        Literal[
            "direct_answer",
            "benefit",
            "conditions",
            "how_to_apply",
            "next_steps",
            "required_documents",
            "limitations",
        ]
    ] = None
    citation_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("citation_ids")
    @classmethod
    def reject_duplicate_citations(cls, value: list[str]) -> list[str]:
        if any(not citation_id.strip() for citation_id in value):
            raise ValueError("section citation IDs must not be blank")
        if len(value) != len(set(value)):
            raise ValueError("section citation IDs must be unique")
        return value


class OfficialLink(BaseModel):
    kind: Literal["application", "status", "help"]
    label: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def require_web_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("official link must be an absolute HTTP(S) URL")
        return value


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list, max_length=5)
    sections: list[AnswerSection] = Field(default_factory=list, max_length=12)
    official_links: list[OfficialLink] = Field(default_factory=list, max_length=6)
    route: Optional[str] = None
    confidence: Optional[float] = None
    response_status: Literal[
        "answered", "abstained", "clarification_needed", "eligibility_unverified"
    ] = "answered"

    @field_validator("citations")
    @classmethod
    def reject_duplicate_citations(cls, value: list[Citation]) -> list[Citation]:
        chunk_ids = [citation.chunk_id for citation in value]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("citation chunk IDs must be unique")
        return value

    @model_validator(mode="after")
    def validate_section_citations(self):
        retrieved_ids = {citation.chunk_id for citation in self.citations}
        if any(
            citation_id not in retrieved_ids
            for section in self.sections
            for citation_id in section.citation_ids
        ):
            raise ValueError("section citation ID is not present in citations")
        return self


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
