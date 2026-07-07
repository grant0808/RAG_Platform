from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FOUNDRY_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Foundry API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    data_dir: Path = Path(".data")
    database_url: str = "sqlite+aiosqlite:///./.data/foundry.db"
    vector_store_provider: str = Field(
        default="chroma",
        validation_alias=AliasChoices(
            "vector_store_provider",
            "FOUNDRY_VECTOR_STORE_PROVIDER",
            "FOUNDRY_VECTOR_STORE_TYPE",
            "VECTOR_STORE_TYPE",
        ),
    )
    vector_database_url: str = "postgresql+psycopg://foundry:foundry@localhost:5432/foundry"
    vector_collection_name: str = "foundry_documents"
    chroma_collection_name: str = Field(
        default="healthcare_pdf_papers",
        validation_alias=AliasChoices(
            "chroma_collection_name",
            "FOUNDRY_CHROMA_COLLECTION_NAME",
            "CHROMA_COLLECTION_NAME",
        ),
    )
    chroma_persist_dir: Path = Field(
        default=Path(".data/chroma"),
        validation_alias=AliasChoices(
            "chroma_persist_dir",
            "FOUNDRY_CHROMA_PERSIST_DIR",
            "CHROMA_PERSIST_DIR",
            "FOUNDRY_VECTOR_STORE_DIR",
            "VECTOR_STORE_DIR",
        ),
    )
    rag_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("rag_enabled", "FOUNDRY_RAG_ENABLED", "RAG_ENABLED"),
    )
    embedding_provider: str = "huggingface"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_api_key: SecretStr | None = None
    huggingface_embedding_model: str = Field(
        default="BAAI/bge-m3",
        validation_alias=AliasChoices(
            "huggingface_embedding_model",
            "FOUNDRY_HUGGINGFACE_EMBEDDING_MODEL",
            "FOUNDRY_EMBEDDING_MODEL_NAME",
            "EMBEDDING_MODEL_NAME",
        ),
    )
    pdf_parser: str = "docling"
    rebuild_index_on_startup: bool = True
    docling_chunker_max_tokens: int = 512
    docling_chunker_merge_peers: bool = True
    source_paper_dir: Path = Field(
        default=Path("source/papers"),
        validation_alias=AliasChoices(
            "source_paper_dir",
            "FOUNDRY_SOURCE_PAPER_DIR",
            "SOURCE_PAPER_DIR",
        ),
    )
    rag_top_k: int = Field(
        default=10,
        validation_alias=AliasChoices("rag_top_k", "FOUNDRY_RAG_TOP_K", "RAG_TOP_K"),
    )
    final_context_top_k: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "final_context_top_k",
            "FOUNDRY_FINAL_CONTEXT_TOP_K",
            "FINAL_CONTEXT_TOP_K",
        ),
    )
    rag_score_threshold: float = Field(
        default=0.35,
        validation_alias=AliasChoices(
            "rag_score_threshold",
            "FOUNDRY_RAG_SCORE_THRESHOLD",
            "RAG_SCORE_THRESHOLD",
        ),
    )
    web_search_provider: str = Field(
        default="dummy",
        validation_alias=AliasChoices(
            "web_search_provider",
            "FOUNDRY_WEB_SEARCH_PROVIDER",
            "WEB_SEARCH_PROVIDER",
        ),
    )
    tavily_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("tavily_api_key", "FOUNDRY_TAVILY_API_KEY", "TAVILY_API_KEY"),
    )
    ragas_results_dir: Path = Field(
        default=Path(".data/evaluations"),
        validation_alias=AliasChoices(
            "ragas_results_dir",
            "FOUNDRY_RAGAS_RESULTS_DIR",
            "RAGAS_RESULTS_DIR",
        ),
    )
    bm25_index_dir: Path = Field(
        default=Path(".data/bm25"),
        validation_alias=AliasChoices(
            "bm25_index_dir",
            "FOUNDRY_BM25_INDEX_DIR",
            "BM25_INDEX_DIR",
        ),
    )
    kiwi_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("kiwi_enabled", "FOUNDRY_KIWI_ENABLED", "KIWI_ENABLED"),
    )
    rrf_k: int = Field(
        default=60,
        validation_alias=AliasChoices("rrf_k", "FOUNDRY_RRF_K", "RRF_K"),
    )
    reranker_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "reranker_enabled",
            "FOUNDRY_RERANKER_ENABLED",
            "RERANKER_ENABLED",
        ),
    )
    reranker_model_name: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        validation_alias=AliasChoices(
            "reranker_model_name",
            "FOUNDRY_RERANKER_MODEL_NAME",
            "RERANKER_MODEL_NAME",
        ),
    )
    reranker_load_model: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "reranker_load_model",
            "FOUNDRY_RERANKER_LOAD_MODEL",
            "RERANKER_LOAD_MODEL",
        ),
    )
    rerank_top_n: int = Field(
        default=10,
        validation_alias=AliasChoices("rerank_top_n", "FOUNDRY_RERANK_TOP_N", "RERANK_TOP_N"),
    )
    rerank_score_threshold: float = Field(
        default=0.2,
        validation_alias=AliasChoices(
            "rerank_score_threshold",
            "FOUNDRY_RERANK_SCORE_THRESHOLD",
            "RERANK_SCORE_THRESHOLD",
        ),
    )
    min_context_count: int = Field(
        default=2,
        validation_alias=AliasChoices(
            "min_context_count",
            "FOUNDRY_MIN_CONTEXT_COUNT",
            "MIN_CONTEXT_COUNT",
        ),
    )
    web_fallback_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "web_fallback_enabled",
            "FOUNDRY_WEB_FALLBACK_ENABLED",
            "WEB_FALLBACK_ENABLED",
        ),
    )
    web_fallback_provider: str = Field(
        default="duckduckgo",
        validation_alias=AliasChoices(
            "web_fallback_provider",
            "FOUNDRY_WEB_FALLBACK_PROVIDER",
            "WEB_FALLBACK_PROVIDER",
        ),
    )
    web_fallback_on_empty_context: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "web_fallback_on_empty_context",
            "FOUNDRY_WEB_FALLBACK_ON_EMPTY_CONTEXT",
            "WEB_FALLBACK_ON_EMPTY_CONTEXT",
        ),
    )
    duckduckgo_max_results: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "duckduckgo_max_results",
            "FOUNDRY_DUCKDUCKGO_MAX_RESULTS",
            "DUCKDUCKGO_MAX_RESULTS",
        ),
    )
    langgraph_trace_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "langgraph_trace_enabled",
            "FOUNDRY_LANGGRAPH_TRACE_ENABLED",
            "LANGGRAPH_TRACE_ENABLED",
        ),
    )
    openai_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4o-mini"
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices(
            "ollama_base_url",
            "FOUNDRY_OLLAMA_BASE_URL",
            "OLLAMA_BASE_URL",
        ),
    )
    ollama_chat_model: str = "llama3.1"
    master_key_path: Path = Path(".data/master.key")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:4173"]
    )
    provider_timeout_seconds: float = 20.0
    max_upload_bytes: int = 20 * 1024 * 1024
    chunk_size: int = Field(
        default=1000,
        validation_alias=AliasChoices(
            "chunk_size",
            "FOUNDRY_CHUNK_SIZE",
            "FOUNDRY_RAG_CHUNK_SIZE",
            "RAG_CHUNK_SIZE",
        ),
    )
    chunk_overlap: int = Field(
        default=150,
        validation_alias=AliasChoices(
            "chunk_overlap",
            "FOUNDRY_CHUNK_OVERLAP",
            "FOUNDRY_RAG_CHUNK_OVERLAP",
            "RAG_CHUNK_OVERLAP",
        ),
    )
    fake_llm_enabled: bool = False
    fallback_to_local_model_on_provider_quota: bool = True
    chat_session_token_budget: int = 100_000
    openai_admin_api_key: SecretStr | None = None
    anthropic_admin_api_key: SecretStr | None = None

    def prepare_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
        self.source_paper_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.bm25_index_dir.mkdir(parents=True, exist_ok=True)
        self.ragas_results_dir.mkdir(parents=True, exist_ok=True)
        self.master_key_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
