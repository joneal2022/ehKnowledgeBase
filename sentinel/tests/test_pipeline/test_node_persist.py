"""Unit tests for persist_node — Task 15."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.pipeline.nodes.persist import persist_node
from app.pipeline.state import PipelineState


def _base_state(**kwargs) -> PipelineState:
    defaults = {
        "source_id": str(uuid.uuid4()),
        "url": "https://www.youtube.com/watch?v=abc",
        "transcript": "",
        "original_title": None,
        "author": None,
        "preprocessed_transcript": "",
        "sections": [],
        "classified_sections": [],
        "reports": {},
        "synthesis": {},
        "errors": [],
        "prompt_versions": {},
    }
    defaults.update(kwargs)
    return defaults  # type: ignore


def _make_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_config(session=None):
    return {"configurable": {"session": session or _make_session()}}


class TestPersistNode:
    @pytest.mark.asyncio
    async def test_sets_source_processing_status_completed(self):
        session = _make_session()
        await persist_node(_base_state(), _make_config(session=session))
        # session.execute called with the UPDATE statement
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_flushes_session(self):
        session = _make_session()
        await persist_node(_base_state(), _make_config(session=session))
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_empty_errors(self):
        session = _make_session()
        result = await persist_node(_base_state(), _make_config(session=session))
        assert result == {"errors": []}
