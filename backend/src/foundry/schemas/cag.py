from datetime import datetime

from pydantic import BaseModel, Field


class CacheEntryResponse(BaseModel):
    key: str
    answer: str
    expires_at_timestamp: float
    expires_at: datetime
    ttl_seconds_remaining: float


class CacheCreateRequest(BaseModel):
    key: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    ttl_seconds: int = Field(default=300, ge=1)
