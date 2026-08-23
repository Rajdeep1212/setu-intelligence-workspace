from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://setu:setu@localhost:5432/setu"
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    mlflow_tracking_uri: str = "./mlruns"


settings = Settings()
