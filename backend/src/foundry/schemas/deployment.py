from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from foundry.schemas.base import OrmModel


class DeploymentCreate(BaseModel):
    pipeline_id: str
    slug: str | None = Field(default=None, min_length=3, max_length=80)
    status: Literal["preview", "production"] = "preview"

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if not normalized.replace("-", "").isalnum():
            raise ValueError("slug must contain only letters, numbers, and hyphens")
        return normalized


class DeploymentResponse(OrmModel):
    id: str
    pipeline_id: str
    slug: str
    version: int
    status: str
    created_at: datetime
