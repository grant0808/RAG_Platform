from pydantic import BaseModel, Field

from foundry.schemas.base import Citation, StrategyName, TraceEvent


class ChatRequest(BaseModel):
    pipeline_id: str
    message: str = Field(min_length=1, max_length=20_000)
    strategy: StrategyName | None = None


class PublicChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    strategy: StrategyName | None = None


class ChatResponse(BaseModel):
    answer: str
    strategy: str
    provider: str
    model: str
    citations: list[Citation] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    cached: bool = False
