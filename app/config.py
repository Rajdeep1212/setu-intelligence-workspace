from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


OPENVINO_MODELS = ("bge-m3", "bge-reranker-v2-m3")
OPENVINO_REQUIRED_FILES = (
    "config.json",
    "openvino_model.xml",
    "openvino_model.bin",
    "tokenizer.json",
    "tokenizer_config.json",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: str = "postgresql+asyncpg://setu:setu@localhost:5432/setu"
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    mlflow_tracking_uri: str = "./mlruns"
    local_inference_backend: Literal["pytorch", "openvino"] = "pytorch"
    openvino_model_dir: str = "/models/openvino"
    setu_api_key: SecretStr | None = None
    query_rate_limit: int = Field(default=10, ge=1, le=10_000)
    query_rate_window_seconds: int = Field(default=60, ge=1, le=86_400)
    max_request_body_bytes: int = Field(default=16_384, ge=1_024, le=1_048_576)
    cors_allowed_origins: str = "http://localhost:3000"
    groq_request_timeout_seconds: float = Field(default=600, ge=1, le=3_600)
    groq_connect_timeout_seconds: float = Field(default=5, ge=1, le=60)
    groq_max_retries: int = Field(default=2, ge=0, le=5)
    database_pool_size: int = Field(default=5, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_timeout_seconds: float = Field(default=30, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=1_800, ge=60, le=86_400)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            url = make_url(value)
        except Exception as exc:
            raise ValueError(
                "DATABASE_URL must be a valid SQLAlchemy URL"
            ) from exc
        if url.drivername != "postgresql+asyncpg" or not url.host or not url.database:
            raise ValueError(
                "DATABASE_URL must use postgresql+asyncpg and include host and database"
            )
        return value

    @field_validator("openvino_model_dir")
    @classmethod
    def validate_openvino_model_dir(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("OPENVINO_MODEL_DIR must not be empty")
        return value

    @field_validator("setu_api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",")]
        origins = [origin for origin in origins if origin]
        for origin in origins:
            if origin == "*":
                raise ValueError("CORS_ALLOWED_ORIGINS must not contain a wildcard")
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS entries must be HTTP(S) origins"
                )
        return ",".join(origins)

    @property
    def cors_origins(self) -> list[str]:
        return [origin for origin in self.cors_allowed_origins.split(",") if origin]

    @property
    def llm_provider(self) -> str | None:
        if self.groq_api_key:
            return "groq"
        if self.gemini_api_key:
            return "gemini"
        return None

    def openvino_artifacts_ready(self) -> bool:
        if self.local_inference_backend != "openvino":
            return True
        root = Path(self.openvino_model_dir)
        return all(
            (root / model / filename).is_file()
            for model in OPENVINO_MODELS
            for filename in OPENVINO_REQUIRED_FILES
        )

    def operational_issues(self) -> list[str]:
        issues: list[str] = []
        if self.setu_api_key is None:
            issues.append("api_auth_not_configured")
        if self.llm_provider is None:
            issues.append("llm_not_configured")
        if not self.openvino_artifacts_ready():
            issues.append("openvino_artifacts_missing")
        return issues


settings = Settings()
