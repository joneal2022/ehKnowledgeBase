"""Unit tests for domain filter view + reprocess endpoint — Task 20."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models.job import ProcessingJob
from app.models.source import ProcessingStatus, Source, SourceType


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_source(status=ProcessingStatus.completed):
    src = MagicMock(spec=Source)
    src.id = uuid.uuid4()
    src.source_type = SourceType.youtube
    src.url = "https://www.youtube.com/watch?v=test"
    src.title = "RAG Architecture Deep Dive"
    src.original_title = "Live Recording"
    src.author = None
    src.processing_status = status
    src.published_at = None
    src.created_at = datetime.now(timezone.utc)
    return src


def _mock_run_pipeline():
    mock = MagicMock()
    mock.delay.return_value = MagicMock(id="task-id-retry")
    return mock


def _override_domain_session(sources=None):
    """Session that returns sources list from scalars().all()."""
    _sources = sources or []

    async def _get_session():
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = _sources
        session.execute = AsyncMock(return_value=result)
        yield session

    return _get_session


def _override_reprocess_session(source=None, added=None):
    """Session for reprocess tests."""
    _added = added if added is not None else []

    async def _get_session():
        session = AsyncMock()
        session.add = MagicMock(side_effect=_added.append)
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        src_result = MagicMock()
        src_result.scalar_one_or_none.return_value = source
        session.execute = AsyncMock(return_value=src_result)
        yield session

    return _get_session


# ── Domain filter view tests ──────────────────────────────────────────────────

class TestDomainView:
    def test_returns_200_for_valid_domain(self):
        app.dependency_overrides[get_session] = _override_domain_session()
        try:
            resp = TestClient(app).get("/domain/dev_tooling")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200

    def test_returns_404_for_invalid_domain(self):
        app.dependency_overrides[get_session] = _override_domain_session()
        try:
            resp = TestClient(app).get("/domain/not_a_domain")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 404

    def test_returns_404_for_not_relevant(self):
        """not_relevant is not a valid filter domain for users."""
        app.dependency_overrides[get_session] = _override_domain_session()
        try:
            resp = TestClient(app).get("/domain/not_relevant")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 404

    def test_shows_domain_label_in_heading(self):
        app.dependency_overrides[get_session] = _override_domain_session()
        try:
            resp = TestClient(app).get("/domain/ai_solutions")
        finally:
            app.dependency_overrides.clear()
        assert "AI Solutions" in resp.text

    def test_shows_source_title_when_sources_exist(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_domain_session(sources=[source])
        try:
            resp = TestClient(app).get("/domain/dev_tooling")
        finally:
            app.dependency_overrides.clear()
        assert "RAG Architecture Deep Dive" in resp.text

    def test_shows_empty_state_when_no_sources(self):
        app.dependency_overrides[get_session] = _override_domain_session(sources=[])
        try:
            resp = TestClient(app).get("/domain/business_dev")
        finally:
            app.dependency_overrides.clear()
        assert "No videos for" in resp.text

    def test_returns_html(self):
        app.dependency_overrides[get_session] = _override_domain_session()
        try:
            resp = TestClient(app).get("/domain/dev_tooling")
        finally:
            app.dependency_overrides.clear()
        assert "text/html" in resp.headers["content-type"]


# ── Reprocess endpoint tests ──────────────────────────────────────────────────

class TestReprocessEndpoint:
    def test_returns_202_for_existing_source(self):
        source = _make_source(status=ProcessingStatus.failed)
        added = []
        app.dependency_overrides[get_session] = _override_reprocess_session(
            source=source, added=added
        )
        try:
            with patch("app.api.sources.run_pipeline", _mock_run_pipeline()):
                resp = TestClient(app).post(f"/api/sources/{source.id}/reprocess")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 202

    def test_returns_404_for_unknown_source(self):
        app.dependency_overrides[get_session] = _override_reprocess_session(source=None)
        try:
            with patch("app.api.sources.run_pipeline", _mock_run_pipeline()):
                resp = TestClient(app).post(f"/api/sources/{uuid.uuid4()}/reprocess")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 404

    def test_creates_new_processing_job(self):
        source = _make_source(status=ProcessingStatus.failed)
        added = []
        app.dependency_overrides[get_session] = _override_reprocess_session(
            source=source, added=added
        )
        try:
            with patch("app.api.sources.run_pipeline", _mock_run_pipeline()):
                TestClient(app).post(f"/api/sources/{source.id}/reprocess")
        finally:
            app.dependency_overrides.clear()
        job_rows = [o for o in added if isinstance(o, ProcessingJob)]
        assert len(job_rows) == 1

    def test_sets_hx_trigger_header(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_reprocess_session(source=source)
        try:
            with patch("app.api.sources.run_pipeline", _mock_run_pipeline()):
                resp = TestClient(app).post(f"/api/sources/{source.id}/reprocess")
        finally:
            app.dependency_overrides.clear()
        assert resp.headers.get("hx-trigger") == "refreshSources"

    def test_enqueues_run_pipeline(self):
        source = _make_source()
        app.dependency_overrides[get_session] = _override_reprocess_session(source=source)
        mock_pipeline = _mock_run_pipeline()
        try:
            with patch("app.api.sources.run_pipeline", mock_pipeline):
                TestClient(app).post(f"/api/sources/{source.id}/reprocess")
        finally:
            app.dependency_overrides.clear()
        mock_pipeline.delay.assert_called_once()
