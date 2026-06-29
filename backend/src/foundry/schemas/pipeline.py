from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from foundry.schemas.base import OrmModel, ProviderName, StrategyName

DEFAULT_OPENAI_CHAT_MODEL = "gpt-4o-mini"


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    strategy: StrategyName = "rag"
    provider: ProviderName = "openai"
    model: str = Field(default=DEFAULT_OPENAI_CHAT_MODEL, min_length=1, max_length=120)
    system_prompt: str = Field(
        default="Answer only from the supplied context and cite the source metadata.",
        min_length=1,
        max_length=10_000,
    )
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.2, ge=0, le=1)


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    strategy: StrategyName | None = None
    provider: ProviderName | None = None
    model: str | None = Field(default=None, min_length=1, max_length=120)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=10_000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=0, le=1)


class PipelineResponse(OrmModel):
    id: str
    name: str
    strategy: str
    provider: str
    model: str
    system_prompt: str
    top_k: int
    similarity_threshold: float
    current_version: int
    created_at: datetime
    updated_at: datetime


class PipelineVersionResponse(OrmModel):
    id: str
    pipeline_id: str
    version: int
    config: dict[str, Any]
    created_at: datetime
