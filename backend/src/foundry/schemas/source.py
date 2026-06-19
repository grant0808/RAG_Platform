from datetime import datetime

from foundry.schemas.base import OrmModel


class SourceResponse(OrmModel):
    id: str
    name: str
    kind: str
    status: str
    table_name: str | None
    chunk_count: int
    size_bytes: int
    created_at: datetime
