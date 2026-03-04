"""Unit tests for feedback API — Task 16."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models.feedback import Feedback, FeedbackTargetType
from app.models.section import ContentSection, DomainEnum
from app.models.source import ProcessingStatus, Source, SourceType


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_source(title="Generated Title"):
    src = MagicMock(spec=Source)
    src.id = uuid.uuid4()
    src.source_type = SourceType.youtube
    src.url = "https://www.youtube.com/watch?v=test"
    src.title = title
    src.original_title = "Live Recording Jan 15"
    src.author = None
    src.processing_status = ProcessingStatus.completed
    src.created_at = datetime.now(timezone.utc)
    src.updated_at = datetime.now(timezone.utc)
    src.raw_content = None
    src.metadata_ = None
    src.published_at = None
    return src


def _make_section(domain=DomainEnum.dev_tooling):
    sec = MagicMock(spec=ContentSection)
    sec.id = uuid.uuid4()
    sec.content = "How to set up CI/CD pipelines."
    sec.domain = domain
    return sec


def _override_session_simple(added=None, execute_returns=None):
    """Simple session override that tracks added objects."""
    _added = added if added is not None else []

    async def _get_session():
        session = AsyncMock()
        session.add = MagicMock(side_effect=_added.append)
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        if execute_returns is not None:
            result = MagicMock()
            result.scalar_one_or_none.return_value = execute_returns
            session.execute = AsyncMock(return_value=result)
        else:
            session.execute = AsyncMock(return_value=MagicMock())

        yield session

    return _get_session


# ── POST /api/feedback ────────────────────────────────────────────────────────

class TestPostFeedback:
    def test_thumbs_up_stores_feedback(self):
        section_id = str(uuid.uuid4())
        added = []
        app.dependency_overrides[get_session] = _override_session_simple(added=added)
        try:
            client = TestClient(app)
            resp = client.post("/api/feedback", json={
                "target_type": "classification",
                "target_id": section_id,
                "rating": 1,
            })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        fb_rows = [o for o in added if isinstance(o, Feedback)]
        assert len(fb_rows) == 1
        assert fb_rows[0].rating == 1

    def test_thumbs_down_with_correction_stores_feedback(self):
        section = _make_section()
        added = []
        app.dependency_overrides[get_session] = _override_session_simple(
            added=added, execute_returns=section
        )
        try:
            with patch("app.api.feedback.PromptEvolutionService") as MockEvol:
                MockEvol.return_value.process_classification_correction = AsyncMock()
                MockEvol.return_value.process_report_rating = AsyncMock()
                client = TestClient(app)
                resp = client.post("/api/feedback", json={
                    "target_type": "classification",
                    "target_id": str(section.id),
                    "rating": 0,
                    "correction": {"correct_domain": "ai_solutions"},
                })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        fb_rows = [o for o in added if isinstance(o, Feedback)]
        assert len(fb_rows) == 1
        assert fb_rows[0].correction == {"correct_domain": "ai_solutions"}

    def test_classification_correction_calls_evolution_service(self):
        section = _make_section()
        added = []
        app.dependency_overrides[get_session] = _override_session_simple(
            added=added, execute_returns=section
        )
        try:
            with patch("app.api.feedback.PromptEvolutionService") as MockEvol:
                mock_instance = AsyncMock()
                MockEvol.return_value = mock_instance
                client = TestClient(app)
                client.post("/api/feedback", json={
                    "target_type": "classification",
                    "target_id": str(section.id),
                    "rating": 0,
                    "correction": {"correct_domain": "ai_solutions"},
                })
        finally:
            app.dependency_overrides.clear()

        mock_instance.process_classification_correction.assert_awaited_once()

    def test_report_rating_stores_feedback(self):
        report_id = str(uuid.uuid4())
        added = []
        app.dependency_overrides[get_session] = _override_session_simple(added=added)
        try:
            with patch("app.api.feedback.PromptEvolutionService") as MockEvol:
                mock_instance = AsyncMock()
                MockEvol.return_value = mock_instance
                client = TestClient(app)
                resp = client.post("/api/feedback", json={
                    "target_type": "report",
                    "target_id": report_id,
                    "rating": 4,
                })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        fb_rows = [o for o in added if isinstance(o, Feedback)]
        assert len(fb_rows) == 1
        assert fb_rows[0].rating == 4

    def test_invalid_target_type_returns_422(self):
        app.dependency_overrides[get_session] = _override_session_simple()
        try:
            client = TestClient(app)
            resp = client.post("/api/feedback", json={
                "target_type": "invalid_type",
                "target_id": str(uuid.uuid4()),
                "rating": 1,
            })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 422

    def test_response_is_html_fragment(self):
        added = []
        app.dependency_overrides[get_session] = _override_session_simple(added=added)
        try:
            client = TestClient(app)
            resp = client.post("/api/feedback", json={
                "target_type": "report",
                "target_id": str(uuid.uuid4()),
                "rating": 5,
            })
        finally:
            app.dependency_overrides.clear()

        assert "text/html" in resp.headers["content-type"]


# ── PATCH /api/sources/{id}/title ─────────────────────────────────────────────

class TestPatchTitle:
    def test_updates_source_title(self):
        source = _make_source(title="Old Generated Title")
        added = []

        async def _get_session():
            session = AsyncMock()
            session.add = MagicMock(side_effect=added.append)
            session.flush = AsyncMock()
            session.commit = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = source
            session.execute = AsyncMock(return_value=result)
            yield session

        app.dependency_overrides[get_session] = _get_session
        try:
            with patch("app.api.feedback.PromptEvolutionService") as MockEvol:
                MockEvol.return_value.process_title_correction = AsyncMock()
                client = TestClient(app)
                resp = client.patch(
                    f"/api/sources/{source.id}/title",
                    json={"title": "New Descriptive Title"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert source.title == "New Descriptive Title"

    def test_stores_title_feedback(self):
        source = _make_source(title="Old Title")
        added = []

        async def _get_session():
            session = AsyncMock()
            session.add = MagicMock(side_effect=added.append)
            session.flush = AsyncMock()
            session.commit = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = source
            session.execute = AsyncMock(return_value=result)
            yield session

        app.dependency_overrides[get_session] = _get_session
        try:
            with patch("app.api.feedback.PromptEvolutionService") as MockEvol:
                MockEvol.return_value.process_title_correction = AsyncMock()
                client = TestClient(app)
                client.patch(
                    f"/api/sources/{source.id}/title",
                    json={"title": "New Title"},
                )
        finally:
            app.dependency_overrides.clear()

        fb_rows = [o for o in added if isinstance(o, Feedback)]
        assert len(fb_rows) == 1
        assert fb_rows[0].correction["new_title"] == "New Title"

    def test_calls_evolution_process_title_correction(self):
        source = _make_source()
        added = []

        async def _get_session():
            session = AsyncMock()
            session.add = MagicMock(side_effect=added.append)
            session.flush = AsyncMock()
            session.commit = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = source
            session.execute = AsyncMock(return_value=result)
            yield session

        app.dependency_overrides[get_session] = _get_session
        try:
            with patch("app.api.feedback.PromptEvolutionService") as MockEvol:
                mock_instance = AsyncMock()
                MockEvol.return_value = mock_instance
                client = TestClient(app)
                client.patch(
                    f"/api/sources/{source.id}/title",
                    json={"title": "Better Title"},
                )
        finally:
            app.dependency_overrides.clear()

        mock_instance.process_title_correction.assert_awaited_once()

    def test_source_not_found_returns_404(self):
        async def _get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            session.execute = AsyncMock(return_value=result)
            yield session

        app.dependency_overrides[get_session] = _get_session
        try:
            client = TestClient(app)
            resp = client.patch(
                f"/api/sources/{uuid.uuid4()}/title",
                json={"title": "New Title"},
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404
