"""Unit tests for video detail page — Task 18."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models.report import Report, ReportType
from app.models.section import ContentSection, DomainEnum
from app.models.source import ProcessingStatus, Source, SourceType


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_source(processing_status=ProcessingStatus.completed):
    src = MagicMock(spec=Source)
    src.id = uuid.uuid4()
    src.source_type = SourceType.youtube
    src.url = "https://www.youtube.com/watch?v=test"
    src.title = "RAG Architecture Deep Dive"
    src.original_title = "Live Recording Jan 15"
    src.author = "Test Author"
    src.processing_status = processing_status
    src.published_at = None
    return src


def _make_report(source_id, report_type=ReportType.domain_specific, domain=DomainEnum.dev_tooling):
    r = MagicMock(spec=Report)
    r.id = uuid.uuid4()
    r.source_id = source_id
    r.report_type = report_type
    r.domain = domain
    r.title = f"{domain.value} Report"
    r.content = "This is the report content."
    r.key_takeaways = ["Takeaway 1", "Takeaway 2"]
    r.action_items = ["Action 1"]
    r.relevance_score = 0.9
    r.model_used = "deepseek-v3"
    r.prompt_version = "abc123"
    r.created_at = datetime.now(timezone.utc)
    return r


def _make_section(source_id, domain=DomainEnum.dev_tooling, index=0):
    s = MagicMock(spec=ContentSection)
    s.id = uuid.uuid4()
    s.source_id = source_id
    s.section_index = index
    s.content = "This section covers CI/CD pipeline setup with GitHub Actions."
    s.domain = domain
    s.classification_confidence = 0.85
    s.needs_review = False
    return s


def _override_session(source=None, reports=None, sections=None):
    """Session override returning different results for each execute call."""
    _reports = reports or []
    _sections = sections or []

    async def _get_session():
        session = AsyncMock()
        session.add = MagicMock()

        source_result = MagicMock()
        source_result.scalar_one_or_none.return_value = source

        reports_result = MagicMock()
        reports_result.scalars.return_value.all.return_value = _reports

        sections_result = MagicMock()
        sections_result.scalars.return_value.all.return_value = _sections

        session.execute = AsyncMock(side_effect=[source_result, reports_result, sections_result])
        yield session

    return _get_session


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestVideoDetailPage:
    def test_returns_200_for_valid_source(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_session(source=source)
        try:
            client = TestClient(app)
            resp = client.get(f"/videos/{source.id}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200

    def test_returns_404_for_unknown_source(self):
        app.dependency_overrides[get_session] = _override_session(source=None)
        try:
            client = TestClient(app)
            resp = client.get(f"/videos/{uuid.uuid4()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    def test_returns_404_for_invalid_uuid(self):
        app.dependency_overrides[get_session] = _override_session(source=None)
        try:
            client = TestClient(app)
            resp = client.get("/videos/not-a-valid-uuid")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    def test_page_contains_source_title(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_session(source=source)
        try:
            client = TestClient(app)
            resp = client.get(f"/videos/{source.id}")
        finally:
            app.dependency_overrides.clear()

        assert "RAG Architecture Deep Dive" in resp.text

    def test_page_shows_processing_banner_when_not_complete(self):
        source = _make_source(processing_status=ProcessingStatus.processing)
        app.dependency_overrides[get_session] = _override_session(source=source)
        try:
            client = TestClient(app)
            resp = client.get(f"/videos/{source.id}")
        finally:
            app.dependency_overrides.clear()

        assert "Pipeline is running" in resp.text

    def test_page_includes_report_content_when_complete(self):
        source = _make_source()
        report = _make_report(source.id)
        section = _make_section(source.id)
        app.dependency_overrides[get_session] = _override_session(
            source=source, reports=[report], sections=[section]
        )
        try:
            client = TestClient(app)
            resp = client.get(f"/videos/{source.id}")
        finally:
            app.dependency_overrides.clear()

        assert "This is the report content." in resp.text

    def test_page_includes_star_rating_widget_for_report(self):
        source = _make_source()
        report = _make_report(source.id)
        app.dependency_overrides[get_session] = _override_session(
            source=source, reports=[report]
        )
        try:
            client = TestClient(app)
            resp = client.get(f"/videos/{source.id}")
        finally:
            app.dependency_overrides.clear()

        assert "feedback-report-" in resp.text
        assert "/api/feedback" in resp.text

    def test_page_includes_classification_feedback_widget_for_sections(self):
        source = _make_source()
        section = _make_section(source.id)
        app.dependency_overrides[get_session] = _override_session(
            source=source, sections=[section]
        )
        try:
            client = TestClient(app)
            resp = client.get(f"/videos/{source.id}")
        finally:
            app.dependency_overrides.clear()

        assert "feedback-classification-" in resp.text

    def test_page_shows_domain_tabs(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_session(source=source)
        try:
            client = TestClient(app)
            resp = client.get(f"/videos/{source.id}")
        finally:
            app.dependency_overrides.clear()

        assert "Dev Tooling" in resp.text
        assert "AI Solutions" in resp.text
        assert "Business Dev" in resp.text
