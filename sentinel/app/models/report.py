import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.section import DomainEnum


class ReportType(str, PyEnum):
    domain_specific = "domain_specific"
    executive_summary = "executive_summary"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), nullable=False)
    domain: Mapped[DomainEnum | None] = mapped_column(Enum(DomainEnum), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)         # markdown
    key_takeaways: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    action_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)       # REQUIRED for Tier 3
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)   # REQUIRED for Tier 3
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
