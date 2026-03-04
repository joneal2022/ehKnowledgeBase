"""Unit tests for segment_node — Task 11."""
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.nodes.segment import segment_node
from app.pipeline.state import PipelineState


def _base_state(**kwargs) -> PipelineState:
    defaults = {
        "source_id": str(uuid.uuid4()),
        "url": "https://www.youtube.com/watch?v=abc",
        "transcript": "raw transcript text",
        "original_title": None,
        "author": None,
        "preprocessed_transcript": "cleaned transcript text",
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
    session.add = MagicMock()   # add() is sync in SQLAlchemy
    session.flush = AsyncMock()
    return session


def _make_config(session=None, llm_client=None):
    return {"configurable": {"session": session or _make_session(), "llm_client": llm_client}}


def _make_prompt_manager():
    mgr = AsyncMock()
    mgr.get_active_prompt = AsyncMock(return_value="{transcript}\n{few_shot_examples}")
    mgr.get_prompt_version_hash = AsyncMock(return_value="seg_hash_001")
    return mgr


SAMPLE_SECTIONS = [
    {"section_index": 0, "content": "intro content", "start_timestamp": "0:00", "end_timestamp": "5:00"},
    {"section_index": 1, "content": "main topic", "start_timestamp": "5:01", "end_timestamp": "12:00"},
]


class TestSegmentNode:
    @pytest.mark.asyncio
    async def test_returns_parsed_sections(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=json.dumps(SAMPLE_SECTIONS))

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await segment_node(_base_state(), _make_config(session=session, llm_client=llm))

        assert len(result["sections"]) == 2

    @pytest.mark.asyncio
    async def test_sections_have_expected_keys(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=json.dumps(SAMPLE_SECTIONS))

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await segment_node(_base_state(), _make_config(session=session, llm_client=llm))

        for sec in result["sections"]:
            assert "section_index" in sec
            assert "content" in sec

    @pytest.mark.asyncio
    async def test_calls_llm_with_segment_task(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=json.dumps(SAMPLE_SECTIONS))

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await segment_node(_base_state(), _make_config(session=session, llm_client=llm))

        llm.complete.assert_awaited_once()
        assert llm.complete.call_args[0][0] == "segment"

    @pytest.mark.asyncio
    async def test_persists_content_sections_to_db(self):
        session = _make_session()
        added = []
        session.add = MagicMock(side_effect=added.append)
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=json.dumps(SAMPLE_SECTIONS))

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await segment_node(_base_state(), _make_config(session=session, llm_client=llm))

        assert len(added) == 2  # one ContentSection per section

    @pytest.mark.asyncio
    async def test_records_prompt_version(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=json.dumps(SAMPLE_SECTIONS))

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await segment_node(_base_state(), _make_config(session=session, llm_client=llm))

        assert result["prompt_versions"]["segment"] == "seg_hash_001"

    @pytest.mark.asyncio
    async def test_empty_transcript_returns_empty_sections(self):
        session = _make_session()
        llm = AsyncMock()

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await segment_node(
                _base_state(transcript="", preprocessed_transcript=""),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_not_awaited()
        assert result["sections"] == []

    @pytest.mark.asyncio
    async def test_llm_parse_failure_returns_error(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="not valid json at all !!!")

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await segment_node(_base_state(), _make_config(session=session, llm_client=llm))

        assert result["sections"] == []
        assert len(result["errors"]) == 1
        assert "segment:" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_uses_preprocessed_transcript_over_raw(self):
        session = _make_session()
        captured = {}

        async def capture_complete(task, prompt, **kw):
            captured["prompt"] = prompt
            return json.dumps(SAMPLE_SECTIONS)

        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=capture_complete)

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await segment_node(
                _base_state(transcript="raw", preprocessed_transcript="cleaned preferred"),
                _make_config(session=session, llm_client=llm),
            )

        assert "cleaned preferred" in captured["prompt"]

    @pytest.mark.asyncio
    async def test_no_errors_on_success(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=json.dumps(SAMPLE_SECTIONS))

        with patch("app.pipeline.nodes.segment.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await segment_node(_base_state(), _make_config(session=session, llm_client=llm))

        assert result["errors"] == []
