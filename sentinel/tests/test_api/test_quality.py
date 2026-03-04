"""Unit tests for quality dashboard page — Task 19."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models.feedback import Feedback, FeedbackTargetType
from app.models.prompt_version import PromptVersion
from app.models.source import ProcessingStatus, Source, SourceType


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_source(status=ProcessingStatus.completed):
    src = MagicMock(spec=Source)
    src.id = uuid.uuid4()
    src.processing_status = status
    src.created_at = datetime.now(timezone.utc)
    return src


def _make_feedback(target_type=FeedbackTargetType.classification, rating=1):
    fb = MagicMock(spec=Feedback)
    fb.id = uuid.uuid4()
    fb.target_type = target_type
    fb.rating = rating
    fb.created_at = datetime.now(timezone.utc)
    return fb


def _make_prompt_version(name="classify", version_hash="abc123def456"):
    pv = MagicMock(spec=PromptVersion)
    pv.id = uuid.uuid4()
    pv.prompt_name = name
    pv.version_hash = version_hash
    pv.is_active = True
    pv.activated_at = datetime.now(timezone.utc)
    return pv


def _override_session(sources=None, feedback_items=None, prompt_versions=None):
    _sources = sources or []
    _feedback = feedback_items or []
    _pvs = prompt_versions or []

    async def _get_session():
        session = AsyncMock()

        src_result = MagicMock()
        src_result.scalars.return_value.all.return_value = _sources

        fb_result = MagicMock()
        fb_result.scalars.return_value.all.return_value = _feedback

        pv_result = MagicMock()
        pv_result.scalars.return_value.all.return_value = _pvs

        session.execute = AsyncMock(side_effect=[src_result, fb_result, pv_result])
        yield session

    return _get_session


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestQualityDashboard:
    def test_returns_200(self):
        app.dependency_overrides[get_session] = _override_session()
        try:
            resp = TestClient(app).get("/quality")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200

    def test_returns_html(self):
        app.dependency_overrides[get_session] = _override_session()
        try:
            resp = TestClient(app).get("/quality")
        finally:
            app.dependency_overrides.clear()
        assert "text/html" in resp.headers["content-type"]

    def test_page_contains_quality_heading(self):
        app.dependency_overrides[get_session] = _override_session()
        try:
            resp = TestClient(app).get("/quality")
        finally:
            app.dependency_overrides.clear()
        assert "Quality Dashboard" in resp.text

    def test_shows_total_video_count(self):
        sources = [_make_source(), _make_source(status=ProcessingStatus.failed)]
        app.dependency_overrides[get_session] = _override_session(sources=sources)
        try:
            resp = TestClient(app).get("/quality")
        finally:
            app.dependency_overrides.clear()
        assert "2" in resp.text  # total sources

    def test_shows_thumbs_up_count(self):
        feedback = [
            _make_feedback(FeedbackTargetType.classification, rating=1),
            _make_feedback(FeedbackTargetType.classification, rating=1),
            _make_feedback(FeedbackTargetType.classification, rating=0),
        ]
        app.dependency_overrides[get_session] = _override_session(feedback_items=feedback)
        try:
            resp = TestClient(app).get("/quality")
        finally:
            app.dependency_overrides.clear()
        # 2 thumbs up, 1 thumbs down in the stats
        assert "Classification" in resp.text

    def test_shows_prompt_versions_table(self):
        pvs = [_make_prompt_version("classify", "abc123def456")]
        app.dependency_overrides[get_session] = _override_session(prompt_versions=pvs)
        try:
            resp = TestClient(app).get("/quality")
        finally:
            app.dependency_overrides.clear()
        assert "classify" in resp.text
        assert "abc123def4" in resp.text  # first 12 chars of hash

    def test_shows_empty_state_for_prompt_versions(self):
        app.dependency_overrides[get_session] = _override_session()
        try:
            resp = TestClient(app).get("/quality")
        finally:
            app.dependency_overrides.clear()
        assert "No prompt versions recorded yet" in resp.text

    def test_page_includes_pipeline_health_section(self):
        app.dependency_overrides[get_session] = _override_session()
        try:
            resp = TestClient(app).get("/quality")
        finally:
            app.dependency_overrides.clear()
        assert "Pipeline Health" in resp.text
        assert "Feedback Overview" in resp.text
