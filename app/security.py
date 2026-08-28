"""Single-process API-key authentication and query rate limiting."""

from __future__ import annotations

import asyncio
import hmac
import logging
import time
from collections import deque
from typing import Annotated, Callable

from fastapi import Header

from app.config import settings
from app.errors import (
    AuthenticationError,
    ConfigurationUnavailableError,
    RateLimitExceededError,
)
from app.observability import get_request_id


logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """Process-local fixed-capacity sliding-window limiter."""

    def __init__(
        self,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._events: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        now = self._clock()
        cutoff = now - self.window_seconds
        async with self._lock:
            while self._events and self._events[0] <= cutoff:
                self._events.popleft()
            if len(self._events) >= self.limit:
                return False
            self._events.append(now)
            return True


query_rate_limiter = InMemoryRateLimiter(
    settings.query_rate_limit,
    settings.query_rate_window_seconds,
)


async def protect_query(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    configured_key = settings.setu_api_key
    if configured_key is None:
        logger.error("api_auth_not_configured request_id=%s", get_request_id())
        raise ConfigurationUnavailableError()

    expected = configured_key.get_secret_value().encode("utf-8")
    supplied = (x_api_key or "").encode("utf-8")
    if not supplied or not hmac.compare_digest(supplied, expected):
        logger.warning("authentication_failed request_id=%s", get_request_id())
        raise AuthenticationError()

    if not await query_rate_limiter.allow():
        logger.warning("rate_limit_exceeded request_id=%s", get_request_id())
        raise RateLimitExceededError()
