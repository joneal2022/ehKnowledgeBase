"""Unit tests for Celery worker and updated POST endpoint — Task 15."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models.job import ProcessingJob
from app.models.source import ProcessingStatus, Source, SourceType


class TestCeleryTask:
    def test_run_pipeline_task_registered(self):
        """run_pipeline task must be registered on celery_app."""
        from app.workers.tasks import celery_app
        assert "run_pipeline" in celery_app.tasks


class TestSourcesPostWithCelery:
    def _make_source(self):
        src = MagicMock(spec=Source)
        src.id = uuid.uuid4()
        src.source_type = SourceType.youtube
        src.url = "https://www.youtube.com/watch?v=test"
        src.title = None
        src.original_title = None
        src.author = None
        src.processing_status = ProcessingStatus.pending
        src.created_at = datetime.now(timezone.utc)
        src.updated_at = datetime.now(timezone.utc)
        src.raw_content = None
        src.metadata_ = None
        src.published_at = None
        return src

    def _override_session(self, source, added):
        async def _get_session():
            session = AsyncMock()
            session.add = MagicMock(side_effect=added.append)
            session.flush = AsyncMock()
            session.commit = AsyncMock()

            async def _refresh(obj):
                for attr in ["id", "source_type", "url", "title", "original_title",
                             "author", "processing_status", "created_at", "updated_at",
                             "raw_content", "metadata_", "published_at"]:
                    setattr(obj, attr, getattr(source, attr))

            session.refresh = AsyncMock(side_effect=_refresh)
            yield session

        return _get_session

    def test_post_creates_processing_job(self):
        """POST /api/sources/youtube should create a ProcessingJob row."""
        source = self._make_source()
        added = []

        mock_task_result = MagicMock()
        mock_task_result.id = "celery-task-id-123"

        app.dependency_overrides[get_session] = self._override_session(source, added)
        try:
            with patch("app.api.sources.run_pipeline") as mock_run_pipeline:
                mock_run_pipeline.delay.return_value = mock_task_result
                client = TestClient(app)
                resp = client.post(
                    "/api/sources/youtube",
                    json={"url": "https://www.youtube.com/watch?v=test"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 202
        job_rows = [o for o in added if isinstance(o, ProcessingJob)]
        assert len(job_rows) == 1

    def test_post_enqueues_pipeline_task(self):
        """POST /api/sources/youtube should call run_pipeline.delay(source_id)."""
        source = self._make_source()
        added = []

        mock_task_result = MagicMock()
        mock_task_result.id = "celery-task-id-456"

        app.dependency_overrides[get_session] = self._override_session(source, added)
        try:
            with patch("app.api.sources.run_pipeline") as mock_run_pipeline:
                mock_run_pipeline.delay.return_value = mock_task_result
                client = TestClient(app)
                client.post(
                    "/api/sources/youtube",
                    json={"url": "https://www.youtube.com/watch?v=test"},
                )
        finally:
            app.dependency_overrides.clear()

        mock_run_pipeline.delay.assert_called_once()
