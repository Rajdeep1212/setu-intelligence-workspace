"""Safe operational errors exposed by the API."""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for failures with a stable, client-safe representation."""

    code = "service_error"
    public_message = "The service could not complete the request."
    status_code = 500


class ConfigurationUnavailableError(ServiceError):
    code = "configuration_unavailable"
    public_message = "The service is not fully configured."
    status_code = 503


class DatabaseUnavailableError(ServiceError):
    code = "database_unavailable"
    public_message = "The database is temporarily unavailable."
    status_code = 503


class RetrievalUnavailableError(ServiceError):
    code = "retrieval_unavailable"
    public_message = "Document retrieval is temporarily unavailable."
    status_code = 503


class LLMProviderError(ServiceError):
    code = "llm_provider_unavailable"
    public_message = "The language-model provider is temporarily unavailable."
    status_code = 502
