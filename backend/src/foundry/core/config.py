from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    master_key_path: Path = Path(".data/master.key")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:4173"]
    )
    provider_timeout_seconds: float = 20.0
    max_upload_bytes: int = 20 * 1024 * 1024
    chunk_size: int = 900
    chunk_overlap: int = 120
    cache_ttl_seconds: int = 300

    def prepare_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
        self.master_key_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
