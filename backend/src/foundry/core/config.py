from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FOUNDRY_",
        extra="ignore",
    )

    app_name: str = "Foundry API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    data_dir: Path = Path(".data")
    database_url: str = "sqlite+aiosqlite:///./.data/foundry.db"
    vector_store_provider: str = "postgres"
    vector_database_url: str = "postgresql+psycopg://foundry:foundry@localhost:5432/foundry"
    vector_collection_name: str = "foundry_documents"
    embedding_provider: str = "openai"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_api_key: SecretStr | None = None
    redis_url: str = "redis://localhost:6379/0"
    master_key_path: Path = Path(".data/master.key")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:4173"]
    )
    provider_timeout_seconds: float = 20.0
    max_upload_bytes: int = 20 * 1024 * 1024
    chunk_size: int = 900
    chunk_overlap: int = 120
    cache_ttl_seconds: int = 300
    fake_llm_enabled: bool = False
    chat_session_token_budget: int = 100_000
    openai_admin_api_key: SecretStr | None = None
    anthropic_admin_api_key: SecretStr | None = None

    def prepare_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
        self.master_key_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
