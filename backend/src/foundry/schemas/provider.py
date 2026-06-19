from datetime import datetime

from pydantic import BaseModel, Field, SecretStr

from foundry.schemas.base import OrmModel


class ProviderConnectRequest(BaseModel):
    api_key: SecretStr = Field(min_length=8)
    validate_connection: bool = True


class ProviderResponse(OrmModel):
    provider: str
    masked_key: str
    status: str
    models: list[str]
    last_validated_at: datetime
