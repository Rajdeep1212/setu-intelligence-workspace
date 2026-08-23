"""
LLM abstraction — Week 3.

Wraps whichever provider you've configured in .env behind one function,
`generate_structured`, using `instructor` to force the response into a
Pydantic model instead of parsing free-text JSON by hand.

Provider selection: set GROQ_API_KEY or GEMINI_API_KEY in .env. If both are
set, Groq is used — its OpenAI-compatible endpoint makes the `instructor`
integration simpler and more stable than Gemini's.

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

from typing import TypeVar

from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

_client = None
_provider: str | None = None


def _get_client():
    global _client, _provider
    if _client is not None:
        return _client, _provider

    import instructor

    if settings.groq_api_key:
        from openai import OpenAI

        raw_client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        _client = instructor.from_openai(raw_client, mode=instructor.Mode.TOOLS)
        _provider = "groq"

    elif settings.gemini_api_key:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        _client = instructor.from_gemini(
            client=genai.GenerativeModel(model_name="gemini-1.5-flash"),
            mode=instructor.Mode.GEMINI_JSON,
        )
        _provider = "gemini"

    else:
        raise RuntimeError(
            "No LLM configured — set GROQ_API_KEY or GEMINI_API_KEY in .env"
        )

    return _client, _provider


def generate_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int = 1024,
) -> T:
    client, provider = _get_client()
    model_name = "llama-3.3-70b-versatile" if provider == "groq" else "gemini-1.5-flash"

    return client.chat.completions.create(
        model=model_name,
        max_tokens=max_tokens,
        response_model=response_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
