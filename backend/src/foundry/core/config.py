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
    vector_store_provider: str = "chroma"
    vector_database_url: str = "postgresql+psycopg://foundry:foundry@localhost:5432/foundry"
    vector_collection_name: str = "foundry_documents"
    chroma_persist_dir: Path = Path(".data/chroma")
    embedding_provider: str = "huggingface"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_api_key: SecretStr | None = None
    huggingface_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    pdf_parser: str = "docling"
    rebuild_index_on_startup: bool = True
    docling_chunker_max_tokens: int = 512
    docling_chunker_merge_peers: bool = True
    openai_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1"
    master_key_path: Path = Path(".data/master.key")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:4173"]
    )
    provider_timeout_seconds: float = 20.0
    max_upload_bytes: int = 20 * 1024 * 1024
    chunk_size: int = 900
    chunk_overlap: int = 120
    fake_llm_enabled: bool = False
    fallback_to_local_model_on_provider_quota: bool = True
    chat_session_token_budget: int = 100_000
    openai_admin_api_key: SecretStr | None = None
    anthropic_admin_api_key: SecretStr | None = None

    def prepare_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.master_key_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
