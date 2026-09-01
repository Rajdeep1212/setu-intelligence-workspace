from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_agent
from app.config import settings
from app.db import engine, get_session
from app.errors import DatabaseUnavailableError, ServiceError
from app.observability import (
    configure_logging,
    get_request_id,
    reset_request_id,
    set_request_id,
)
from app.schemas import (
    AnswerSection,
    Citation,
    ErrorResponse,
    QueryRequest,
    QueryResponse,
    SourceDetail,
    SourcesResponse,
)
from app.security import protect_query, require_api_key
from app.sources import get_source, list_sources


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    issues = settings.operational_issues()
    logger.info(
        "application_startup backend=%s inference_ready=%s llm_provider=%s",
        settings.local_inference_backend,
        settings.openvino_artifacts_ready(),
        settings.llm_provider or "unconfigured",
    )
    if issues:
        logger.warning("configuration_not_ready issues=%s", ",".join(issues))
    try:
        yield
    finally:
        await engine.dispose()
        logger.info("application_shutdown database_pool_disposed=true")


app = FastAPI(title="Setu API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)


def _error_response(
    *, code: str, message: str, status_code: int, request_id: str
) -> JSONResponse:
    payload = ErrorResponse(
        error={"code": code, "message": message, "request_id": request_id}
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


@app.middleware("http")
async def correlate_and_log_request(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    token = set_request_id(request_id)
    started = time.perf_counter()
    try:
        content_length = request.headers.get("content-length")
        request_too_large = (
            request.method == "POST"
            and request.url.path == "/query"
            and content_length is not None
            and content_length.isdigit()
            and int(content_length) > settings.max_request_body_bytes
        )
        if request_too_large:
            logger.warning("request_too_large request_id=%s", request_id)
            response = _error_response(
                code="request_too_large",
                message="The request body is too large.",
                status_code=413,
                request_id=request_id,
            )
        else:
            try:
                response = await call_next(request)
            except Exception as exc:  # final safety boundary; never expose internals
                logger.error(
                    "request_failure request_id=%s method=%s path=%s error_type=%s",
                    request_id,
                    request.method,
                    request.url.path,
                    type(exc).__name__,
                )
                response = _error_response(
                    code="internal_error",
                    message="An internal error occurred.",
                    status_code=500,
                    request_id=request_id,
                )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        duration_ms = (time.perf_counter() - started) * 1000
        log = logger.error if response.status_code >= 500 else logger.info
        log(
            "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    finally:
        reset_request_id(token)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _: Request, __: RequestValidationError
) -> JSONResponse:
    request_id = get_request_id()
    logger.warning("request_validation_failed request_id=%s", request_id)
    return _error_response(
        code="invalid_request",
        message="The request payload is invalid.",
        status_code=422,
        request_id=request_id,
    )


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    request_id = get_request_id()
    logger.error(
        "operation_failed request_id=%s code=%s error_type=%s",
        request_id,
        exc.code,
        type(exc).__name__,
    )
    return _error_response(
        code=exc.code,
        message=exc.public_message,
        status_code=exc.status_code,
        request_id=request_id,
    )


@app.get("/health")
async def health():
    """Liveness only: the API process can receive requests."""
    return {
        "status": "ok",
        "inference_backend": settings.local_inference_backend,
    }


@app.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("database_readiness_failed request_id=%s", get_request_id())
        raise DatabaseUnavailableError() from exc
    if result.scalar() != 1:
        raise DatabaseUnavailableError()
    logger.info("database_ready request_id=%s", get_request_id())
    return {"db": "ok"}


@app.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)):
    """Readiness without eagerly loading multi-gigabyte model weights."""
    issues = settings.operational_issues()
    database_status = "ok"
    try:
        result = await session.execute(text("SELECT 1"))
        if result.scalar() != 1:
            raise DatabaseUnavailableError()
        logger.info("database_ready request_id=%s", get_request_id())
    except (SQLAlchemyError, DatabaseUnavailableError):
        database_status = "error"
        issues.append("database_unavailable")
        logger.error("database_readiness_failed request_id=%s", get_request_id())

    inference_ready = settings.openvino_artifacts_ready()
    status = "ready" if not issues else "not_ready"
    payload = {
        "status": status,
        "database": database_status,
        "inference_backend": settings.local_inference_backend,
        "inference_ready": inference_ready,
        "llm_provider": settings.llm_provider,
    }
    if issues:
        payload["issues"] = issues
    return JSONResponse(status_code=200 if not issues else 503, content=payload)


@app.get(
    "/sources",
    response_model=SourcesResponse,
    dependencies=[Depends(require_api_key)],
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def sources(
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=25)] = 10,
    search: Annotated[str | None, Query(max_length=100)] = None,
    language: Literal["en", "hi", "bn"] | None = None,
    has_eligibility: bool | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await list_sources(
        session,
        page=page,
        page_size=page_size,
        search=search,
        language=language,
        has_eligibility=has_eligibility,
    )


@app.get(
    "/sources/{source_id}",
    response_model=SourceDetail,
    dependencies=[Depends(require_api_key)],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def source_detail(
    source_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_source(session, source_id)


@app.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(protect_query)],
    responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def query(payload: QueryRequest, session: AsyncSession = Depends(get_session)):
    final_state = await run_agent(session, payload.query, language=payload.language)
    citations = [Citation(**citation) for citation in final_state.get("citations", [])]
    return QueryResponse(
        answer=final_state.get("answer", "No answer generated."),
        citations=citations,
        sections=[
            AnswerSection(**section) for section in final_state.get("sections", [])
        ],
        route=final_state.get("route"),
        confidence=final_state.get("confidence"),
        response_status=final_state.get("response_status", "answered"),
    )
