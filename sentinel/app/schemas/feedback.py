"""Feedback request/response schemas."""
from pydantic import BaseModel

from app.models.feedback import FeedbackTargetType


class FeedbackRequest(BaseModel):
    target_type: FeedbackTargetType
    target_id: str          # UUID as string (HTMX hx-vals sends strings)
    rating: int | None = None
    correction: dict | None = None
    notes: str | None = None


class TitlePatchRequest(BaseModel):
    title: str
