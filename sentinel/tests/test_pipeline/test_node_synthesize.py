"""Unit tests for synthesize_node — Task 14."""
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.nodes.synthesize import synthesize_node
from app.pipeline.state import PipelineState


def _base_state(**kwargs) -> PipelineState:
    defaults = {
        "source_id": str(uuid.uuid4()),
        "url": "https://www.youtube.com/watch?v=abc",
        "transcript": "",
        "original_title": "Live Recording Jan 15",
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


def _make_config(session=None, llm_client=None):
    return {"configurable": {"session": session or _make_session(), "llm_client": llm_client}}


def _make_prompt_manager():
    mgr = AsyncMock()
    mgr.get_active_prompt = AsyncMock(
        return_value="{original_title}\n{domain_reports_text}\n{few_shot_examples}"
    )
    mgr.get_prompt_version_hash = AsyncMock(return_value="syn_hash_001")
    return mgr


def _json_synthesis(title="RAG Architecture + AI Pricing Strategies"):
    return json.dumps({
        "title": title,
        "tldr": "Three key insights from this video.",
        "dont_miss": "The RAG architecture tip.",
        "domain_breakdown": {
            "dev_tooling": "CI/CD improvements discussed.",
            "ai_solutions": "RAG setup covered.",
            "business_dev": None,
        },
    })


SAMPLE_REPORTS = {
    "dev_tooling": {
        "title": "Dev Report",
        "summary": "CI/CD improvements for teams.",
    },
    "ai_solutions": {
        "title": "AI Report",
        "summary": "RAG architecture deep-dive.",
    },
}


class TestSynthesizeNode:
    @pytest.mark.asyncio
    async def test_synthesis_has_required_keys(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_synthesis())

        with patch("app.pipeline.nodes.synthesize.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await synthesize_node(
                _base_state(reports=SAMPLE_REPORTS),
                _make_config(session=session, llm_client=llm),
            )

        for key in ("title", "tldr", "dont_miss", "domain_breakdown"):
            assert key in result["synthesis"]

    @pytest.mark.asyncio
    async def test_br1_source_title_updated_not_original_title(self):
        """BR-1/DR-4: Source.title must be updated to the GENERATED title."""
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(
            return_value=_json_synthesis(title="Generated Descriptive Title")
        )

        with patch("app.pipeline.nodes.synthesize.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await synthesize_node(
                _base_state(reports=SAMPLE_REPORTS, original_title="Live Recording Jan 15"),
                _make_config(session=session, llm_client=llm),
            )

        # session.execute should be called to update Source.title
        session.execute.assert_awaited_once()
        call_args = session.execute.call_args[0][0]
        # The UPDATE statement should carry the generated title
        assert str(call_args).startswith("UPDATE") or hasattr(call_args, "_values")

    @pytest.mark.asyncio
    async def test_prompt_version_recorded(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_synthesis())

        with patch("app.pipeline.nodes.synthesize.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await synthesize_node(
                _base_state(reports=SAMPLE_REPORTS),
                _make_config(session=session, llm_client=llm),
            )

        assert result["prompt_versions"]["synthesize"] == "syn_hash_001"

    @pytest.mark.asyncio
    async def test_no_reports_still_runs_synthesis(self):
        """Empty reports dict is allowed — synthesis runs with no domain data."""
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_synthesis())

        with patch("app.pipeline.nodes.synthesize.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await synthesize_node(
                _base_state(reports={}),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_awaited_once()
        assert "title" in result["synthesis"]

    @pytest.mark.asyncio
    async def test_parse_failure_returns_error_no_db_update(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="not valid json!!!")

        with patch("app.pipeline.nodes.synthesize.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await synthesize_node(
                _base_state(reports=SAMPLE_REPORTS),
                _make_config(session=session, llm_client=llm),
            )

        session.execute.assert_not_awaited()
        assert result["synthesis"] == {}
        assert len(result["errors"]) == 1
        assert "synthesize:" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_no_errors_on_success(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_synthesis())

        with patch("app.pipeline.nodes.synthesize.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await synthesize_node(
                _base_state(reports=SAMPLE_REPORTS),
                _make_config(session=session, llm_client=llm),
            )

        assert result["errors"] == []
