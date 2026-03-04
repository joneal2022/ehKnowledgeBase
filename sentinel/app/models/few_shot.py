import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FewShotExample(Base):
    __tablename__ = "few_shot_bank"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)             # "classify", "title", etc.
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    corrected_output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
