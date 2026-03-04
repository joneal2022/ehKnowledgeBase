import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeedbackTargetType(str, PyEnum):
    classification = "classification"
    report = "report"
    chat_response = "chat_response"
    retrieval = "retrieval"
    title = "title"


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_type: Mapped[FeedbackTargetType] = mapped_column(Enum(FeedbackTargetType), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)       # 1=thumbs up, 0=thumbs down, 1-5=stars
    correction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
