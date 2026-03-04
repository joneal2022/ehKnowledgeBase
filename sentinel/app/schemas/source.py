"""Pydantic schemas for source ingestion endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_validator

from app.models.source import ProcessingStatus, SourceType


class YouTubeSubmitRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def must_be_youtube_url(cls, v: str) -> str:
        v = v.strip()
        if not any(host in v for host in ("youtube.com", "youtu.be")):
            raise ValueError("URL must be a YouTube URL (youtube.com or youtu.be)")
        return v


class SourceResponse(BaseModel):
    id: uuid.UUID
    source_type: SourceType
    url: str | None
    title: str | None
    original_title: str | None
    author: str | None
    processing_status: ProcessingStatus
    created_at: datetime

    model_config = {"from_attributes": True}
