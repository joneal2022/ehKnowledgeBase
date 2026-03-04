import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.section import DomainEnum


class ApprovalStatus(str, PyEnum):
    pending_report = "pending_report"
    approved_for_education = "approved_for_education"
    pending_education_review = "pending_education_review"
    approved = "approved"
    rejected = "rejected"


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    domain: Mapped[DomainEnum] = mapped_column(Enum(DomainEnum), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    educational_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.pending_report, nullable=False
    )
    approved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_entries.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[DomainEnum] = mapped_column(Enum(DomainEnum), nullable=False)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    # embedding and search_text columns are added via raw DDL in migration
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
