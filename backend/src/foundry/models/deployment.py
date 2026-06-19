from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from foundry.core.database import Base
from foundry.models.base import new_id, utcnow


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pipeline_id: Mapped[str] = mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="preview")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
