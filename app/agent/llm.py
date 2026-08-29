"""
LLM abstraction — Week 3.

Wraps whichever provider you've configured in .env behind one function,
`generate_structured`. Groq uses its native strict JSON-schema response format;
Gemini continues to use `instructor` to produce a Pydantic model.

Provider selection: set GROQ_API_KEY or GEMINI_API_KEY in .env. If both are
set, Groq is used through its OpenAI-compatible native structured-output API.

A NOTE ON THE GEMINI PATH: unlike Groq (which just speaks the well-established
OpenAI chat-completions format), google-generativeai's structured-output API
has shifted across versions more than most. The Gemini backend below is a
working starting point, but if it errors after a `pip install`, check
instructor's current Gemini docs (https://python.useinstructor.com) against
whatever google-generativeai/instructor versions actually resolved — this
couldn't be tested live against either provider's API from the build
environment.
"""

from __future__ import annotations

import logging
import re
from typing import Literal, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.errors import ConfigurationUnavailableError, LLMProviderError
from app.observability import get_request_id

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

_client = None
_provider: str | None = None
_SAFE_DIAGNOSTIC_TOKEN = re.compile(r"[^A-Za-z0-9_.-]")


def _safe_diagnostic_token(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "unknown"
    return _SAFE_DIAGNOSTIC_TOKEN.sub("_", value)[:80]


def _validation_diagnostics(exc: object) -> list[str]:
    if not isinstance(exc, ValidationError):
        return []
    diagnostics: list[str] = []
    for error in exc.errors(
        include_url=False, include_context=False, include_input=False
    ):
        location = ".".join(
            _safe_diagnostic_token(str(part)) for part in error.get("loc", ())
        )
        category = _safe_diagnostic_token(error.get("type"))
        diagnostics.append(f"{location or 'model'}:{category}")
    return diagnostics


def _exception_diagnostics(exc: Exception) -> dict[str, object]:
    chain: list[str] = []
    validation_errors: list[str] = []
    status: int | str = "unknown"
    provider_type = "unknown"
    provider_code = "unknown"
    attempt_count: int | str = "unknown"
    failed_generation_present = False
    failed_generation_empty: bool | str = "unknown"
    current: BaseException | None = exc
    seen: set[int] = set()

    while current is not None and id(current) not in seen and len(chain) < 12:
        seen.add(id(current))
        chain.append(_safe_diagnostic_token(type(current).__name__))

        current_status = getattr(current, "status_code", None)
        if isinstance(current_status, int):
            status = current_status

        current_attempts = getattr(current, "n_attempts", None)
        if isinstance(current_attempts, int):
            attempt_count = current_attempts

        validation_errors.extend(_validation_diagnostics(current))
        for failed_attempt in getattr(current, "failed_attempts", ()) or ():
            validation_errors.extend(
                _validation_diagnostics(getattr(failed_attempt, "exception", None))
            )

        body = getattr(current, "body", None)
        if isinstance(body, dict):
            provider_error = body.get("error", body)
            if isinstance(provider_error, dict):
                provider_type = _safe_diagnostic_token(provider_error.get("type"))
                provider_code = _safe_diagnostic_token(provider_error.get("code"))
                if "failed_generation" in provider_error:
                    failed_generation_present = True
                    failed_generation_empty = not bool(
                        provider_error.get("failed_generation")
                    )

        current = current.__cause__ or current.__context__

    return {
        "exception_chain": ">".join(chain),
        "http_status": status,
        "provider_error_type": provider_type,
        "provider_error_code": provider_code,
        "attempt_count": attempt_count,
        "validation_errors": ",".join(validation_errors) or "none",
        "failed_generation_present": str(failed_generation_present).lower(),
        "failed_generation_empty": (
            str(failed_generation_empty).lower()
            if isinstance(failed_generation_empty, bool)
            else failed_generation_empty
        ),
    }


def _get_client():
    global _client, _provider
    if _client is not None:
        return _client, _provider

    if settings.groq_api_key:
        from openai import OpenAI

        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=httpx.Timeout(
                timeout=settings.groq_request_timeout_seconds,
                connect=settings.groq_connect_timeout_seconds,
            ),
            max_retries=settings.groq_max_retries,
        )
        _provider = "groq"

    elif settings.gemini_api_key:
        import google.generativeai as genai
        import instructor

        genai.configure(api_key=settings.gemini_api_key)
        _client = instructor.from_gemini(
            client=genai.GenerativeModel(model_name="gemini-1.5-flash"),
            mode=instructor.Mode.GEMINI_JSON,
        )
        _provider = "gemini"

    else:
        logger.error("llm_configuration_missing request_id=%s", get_request_id())
        raise ConfigurationUnavailableError()

    return _client, _provider


def generate_structured(
    *,
    stage: Literal["route_decision", "answer_generation"],
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int = 1024,
) -> T:
    provider = settings.llm_provider or "unconfigured"
    try:
        client, provider = _get_client()
        model_name = (
            "openai/gpt-oss-20b" if provider == "groq" else "gemini-1.5-flash"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if provider == "groq":
            completion = client.chat.completions.parse(
                model=model_name,
                max_tokens=max_tokens,
                response_format=response_model,
                messages=messages,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("structured_response_missing")
            return response_model.model_validate(parsed.model_dump(), strict=True)
        return client.chat.completions.create(
            model=model_name,
            max_tokens=max_tokens,
            response_model=response_model,
            messages=messages,
        )
    except ConfigurationUnavailableError:
        raise
    except Exception as exc:
        diagnostics = _exception_diagnostics(exc)
        logger.error(
            "llm_provider_failure request_id=%s stage=%s "
            "exception_chain=%s http_status=%s provider_error_type=%s "
            "provider_error_code=%s attempt_count=%s validation_errors=%s "
            "failed_generation_present=%s failed_generation_empty=%s",
            get_request_id(),
            stage,
            diagnostics["exception_chain"],
            diagnostics["http_status"],
            diagnostics["provider_error_type"],
            diagnostics["provider_error_code"],
            diagnostics["attempt_count"],
            diagnostics["validation_errors"],
            diagnostics["failed_generation_present"],
            diagnostics["failed_generation_empty"],
        )
        raise LLMProviderError() from exc
