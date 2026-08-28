from pathlib import Path
from typing import Literal

from pydantic import field_validator
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
        if self.llm_provider is None:
            issues.append("llm_not_configured")
        if not self.openvino_artifacts_ready():
            issues.append("openvino_artifacts_missing")
        return issues


settings = Settings()
