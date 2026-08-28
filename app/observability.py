"""Minimal logging and request-correlation helpers."""

from __future__ import annotations

import logging
from contextvars import ContextVar


_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Uvicorn configures logging before importing the app. Setting the package
    # logger explicitly ensures SETU's INFO records reach its existing handler.
    logging.getLogger("app").setLevel(logging.INFO)


def set_request_id(request_id: str):
    return _request_id.set(request_id)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()
