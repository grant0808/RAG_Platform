from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from foundry.schemas.base import Citation, StrategyName, TraceEvent


class ChatRequest(BaseModel):
    pipeline_id: str
    message: str = Field(min_length=1, max_length=20_000)
    strategy: StrategyName | None = None
    session_id: str | None = None


class PublicChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    strategy: StrategyName | None = None


class ChatResponse(BaseModel):
    session_id: str | None = None
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
    token_status: dict[str, int] | None = None
    provider_quota: dict[str, Any] | None = None
