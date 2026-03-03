import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DomainEnum(str, PyEnum):
    dev_tooling = "dev_tooling"
    ai_solutions = "ai_solutions"
    business_dev = "business_dev"
    not_relevant = "not_relevant"


class ContentSection(Base):
    __tablename__ = "content_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_timestamp: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_timestamp: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[DomainEnum | None] = mapped_column(Enum(DomainEnum), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    escalated_to_cloud: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
