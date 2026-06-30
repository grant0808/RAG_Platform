from datetime import datetime

from pydantic import BaseModel, Field, SecretStr

from foundry.schemas.base import OrmModel


class ProviderConnectRequest(BaseModel):
    api_key: SecretStr = Field(default=SecretStr(""), min_length=0)
    validate_connection: bool = True


class ProviderResponse(OrmModel):
    provider: str
    masked_key: str
    status: str
    models: list[str]
    last_validated_at: datetime
