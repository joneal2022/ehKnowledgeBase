"""Unit tests for sources API — Task 8."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models.source import ProcessingStatus, Source, SourceType
from app.schemas.source import YouTubeSubmitRequest


def _make_source(**kwargs) -> Source:
    defaults = dict(
        id=uuid.uuid4(),
        source_type=SourceType.youtube,
        url="https://www.youtube.com/watch?v=abc123",
        title=None,
        original_title="Live Recording 2026-01-01",
        author=None,
        processing_status=ProcessingStatus.pending,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        raw_content=None,
        metadata_=None,
        published_at=None,
    )
    for k, v in kwargs.items():
        defaults[k] = v
    src = MagicMock(spec=Source)
    for k, v in defaults.items():
        setattr(src, k, v)
    return src


def _mock_session(sources=None, added_source=None):
    """Build a mock AsyncSession for sources API tests."""
    sources = sources or []
    session = AsyncMock()

    # list query
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = sources
    session.execute = AsyncMock(return_value=list_result)

    session.add = MagicMock()
    session.commit = AsyncMock()

    # refresh populates the source object
    if added_source:
        session.refresh = AsyncMock(side_effect=lambda obj: None)
    else:
        session.refresh = AsyncMock()

    return session


def _override_with_source(source: Source):
    """Override that captures session.add() and sets the source on refresh."""
    async def _get_session():
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        session.add = MagicMock()
        session.commit = AsyncMock()

        async def _refresh(obj):
            # Copy attributes from our prepared source onto the obj being refreshed
            for attr in ["id", "source_type", "url", "title", "original_title",
                         "author", "processing_status", "created_at", "updated_at",
                         "raw_content", "metadata_", "published_at"]:
                setattr(obj, attr, getattr(source, attr))

        session.refresh = AsyncMock(side_effect=_refresh)
        yield session

    return _get_session


def _override_empty():
    async def _get_session():
        yield _mock_session()
    return _get_session


def _override_list(sources):
    async def _get_session():
        yield _mock_session(sources=sources)
    return _get_session


# ── YouTubeSubmitRequest validation ───────────────────────────────────────────

class TestYouTubeSubmitRequest:
    def test_accepts_standard_watch_url(self):
        req = YouTubeSubmitRequest(url="https://www.youtube.com/watch?v=abc123")
        assert req.url == "https://www.youtube.com/watch?v=abc123"

    def test_accepts_youtu_be_short_url(self):
        req = YouTubeSubmitRequest(url="https://youtu.be/abc123")
        assert req.url == "https://youtu.be/abc123"

    def test_strips_whitespace(self):
        req = YouTubeSubmitRequest(url="  https://www.youtube.com/watch?v=abc123  ")
        assert req.url == "https://www.youtube.com/watch?v=abc123"

    def test_rejects_non_youtube_url(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="YouTube"):
            YouTubeSubmitRequest(url="https://vimeo.com/123456")

    def test_rejects_random_string(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            YouTubeSubmitRequest(url="not-a-url-at-all")


# ── POST /api/sources/youtube ─────────────────────────────────────────────────

class TestSubmitYouTubeUrl:
    def test_valid_url_returns_202(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_with_source(source)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/sources/youtube",
                    json={"url": "https://www.youtube.com/watch?v=abc123"},
                )
            assert response.status_code == 202
        finally:
            app.dependency_overrides.clear()

    def test_valid_url_returns_source_id(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_with_source(source)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/sources/youtube",
                    json={"url": "https://www.youtube.com/watch?v=abc123"},
                )
            data = response.json()
            assert "id" in data
        finally:
            app.dependency_overrides.clear()

    def test_valid_url_returns_pending_status(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_with_source(source)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/sources/youtube",
                    json={"url": "https://www.youtube.com/watch?v=abc123"},
                )
            data = response.json()
            assert data["processing_status"] == "pending"
        finally:
            app.dependency_overrides.clear()

    def test_response_has_hx_trigger_header(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_with_source(source)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/sources/youtube",
                    json={"url": "https://www.youtube.com/watch?v=abc123"},
                )
            assert response.headers.get("hx-trigger") == "refreshSources"
        finally:
            app.dependency_overrides.clear()

    def test_non_youtube_url_returns_422(self):
        app.dependency_overrides[get_session] = _override_empty()
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/sources/youtube",
                    json={"url": "https://vimeo.com/123456"},
                )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_missing_url_returns_422(self):
        app.dependency_overrides[get_session] = _override_empty()
        try:
            with TestClient(app) as client:
                response = client.post("/api/sources/youtube", json={})
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_empty_body_returns_422(self):
        app.dependency_overrides[get_session] = _override_empty()
        try:
            with TestClient(app) as client:
                response = client.post("/api/sources/youtube", content=b"")
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ── GET /api/sources ──────────────────────────────────────────────────────────

class TestListSources:
    def test_returns_200(self):
        app.dependency_overrides[get_session] = _override_list([])
        try:
            with TestClient(app) as client:
                response = client.get("/api/sources")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_returns_empty_list_when_no_sources(self):
        app.dependency_overrides[get_session] = _override_list([])
        try:
            with TestClient(app) as client:
                response = client.get("/api/sources")
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    def test_returns_list_with_sources(self):
        sources = [_make_source(), _make_source()]
        app.dependency_overrides[get_session] = _override_list(sources)
        try:
            with TestClient(app) as client:
                response = client.get("/api/sources")
            data = response.json()
            assert len(data) == 2
        finally:
            app.dependency_overrides.clear()

    def test_each_source_has_required_fields(self):
        sources = [_make_source()]
        app.dependency_overrides[get_session] = _override_list(sources)
        try:
            with TestClient(app) as client:
                response = client.get("/api/sources")
            item = response.json()[0]
            assert "id" in item
            assert "processing_status" in item
            assert "source_type" in item
            assert "created_at" in item
        finally:
            app.dependency_overrides.clear()
