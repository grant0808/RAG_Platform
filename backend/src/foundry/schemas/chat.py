from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from foundry.schemas.base import Citation, StrategyName, TraceEvent


class ChatRequest(BaseModel):
    pipeline_id: str
    message: str | None = Field(default=None, min_length=1, max_length=20_000)
    query: str | None = Field(default=None, min_length=1, max_length=20_000)
    strategy: StrategyName | None = None
    session_id: str | None = None
    conversation_id: str | None = None

    @model_validator(mode="after")
    def normalize_aliases(self) -> "ChatRequest":
        if self.message is None:
            self.message = self.query
        if self.query is None:
            self.query = self.message
        if self.session_id is None:
            self.session_id = self.conversation_id
        if self.conversation_id is None:
            self.conversation_id = self.session_id
        if self.message is None:
            raise ValueError("message or query is required")
        return self


class PublicChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    strategy: StrategyName | None = None


class ChatResponse(BaseModel):
    session_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    query: str | None = None
    rewritten_query: str | None = None
    route: str = "rag"
    selected_tool: str | None = None
    answer: str
    strategy: str
    provider: str
    model: str
    model_name: str | None = None
    embedding_model: str | None = None
    reranker_model: str | None = None
    contexts: list[Any] = Field(default_factory=list)
    web_results: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float | None = None
    created_at: datetime | None = None
    cached: bool = False
    memory_used: bool = False
    history_count: int = 0
    token_status: dict[str, int] | None = None
    provider_quota: dict[str, Any] | None = None
