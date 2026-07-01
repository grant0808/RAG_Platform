from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["openai", "anthropic", "ollama"]
StrategyName = Literal["rag"]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Citation(BaseModel):
    source_id: str
    source_name: str
    location: str | None = None
    score: float | None = None


class TraceEvent(BaseModel):
    step: str
    status: Literal["started", "completed", "failed"]
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
