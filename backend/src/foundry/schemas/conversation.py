from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from foundry.schemas.base import OrmModel


class ChatSessionCreate(BaseModel):
    pipeline_id: str
    title: str | None = Field(default=None, min_length=1, max_length=160)


class ChatSessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ChatSessionResponse(OrmModel):
    id: str
    pipeline_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(OrmModel):
    id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    message_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
