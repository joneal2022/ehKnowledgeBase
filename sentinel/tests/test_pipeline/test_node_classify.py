"""Unit tests for classify_node — Task 12."""
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.nodes.classify import classify_node
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
    session.add = MagicMock()  # add() is sync in SQLAlchemy
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_config(session=None, llm_client=None):
    return {"configurable": {"session": session or _make_session(), "llm_client": llm_client}}


def _make_prompt_manager():
    mgr = AsyncMock()
    mgr.get_active_prompt = AsyncMock(
        return_value="{section_content}\n{few_shot_examples}"
    )
    mgr.get_prompt_version_hash = AsyncMock(return_value="cls_hash_001")
    mgr.get_strict_variant = AsyncMock(
        return_value="STRICT: {section_content}\n{few_shot_examples}"
    )
    return mgr


def _json_result(domain="dev_tooling", confidence=0.9, reasoning="clear match"):
    return json.dumps({"domain": domain, "confidence": confidence, "reasoning": reasoning})


SAMPLE_SECTION = {
    "section_index": 0,
    "content": "We discussed how to set up CI/CD pipelines.",
    "start_timestamp": "0:00",
    "end_timestamp": "5:00",
}


class TestClassifyNode:
    @pytest.mark.asyncio
    async def test_happy_path_section_has_domain_confidence_reasoning(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_result())

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=[SAMPLE_SECTION]),
                _make_config(session=session, llm_client=llm),
            )

        assert len(result["classified_sections"]) == 1
        sec = result["classified_sections"][0]
        assert sec["domain"] == "dev_tooling"
        assert sec["confidence"] == 0.9
        assert "reasoning" in sec

    @pytest.mark.asyncio
    async def test_tier1a_strict_retry_on_parse_failure(self):
        """First LLM call returns bad JSON; strict retry succeeds."""
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(
            side_effect=["not valid json!!!", _json_result(domain="ai_solutions", confidence=0.85)]
        )

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=[SAMPLE_SECTION]),
                _make_config(session=session, llm_client=llm),
            )

        assert result["classified_sections"][0]["domain"] == "ai_solutions"
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_tier1a_double_failure_returns_not_relevant(self):
        """Both local attempts fail → not_relevant + needs_review=True."""
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=["bad json", "also bad json"])

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=[SAMPLE_SECTION]),
                _make_config(session=session, llm_client=llm),
            )

        sec = result["classified_sections"][0]
        assert sec["domain"] == "not_relevant"
        assert sec["needs_review"] is True
        assert sec["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_tier1b_cloud_escalation_uses_higher_confidence_result(self):
        """Low local confidence → cloud escalation → cloud result used."""
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(
            side_effect=[
                _json_result(domain="dev_tooling", confidence=0.4),   # local: low
                _json_result(domain="ai_solutions", confidence=0.9),   # cloud: higher
            ]
        )

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=[SAMPLE_SECTION]),
                _make_config(session=session, llm_client=llm),
            )

        sec = result["classified_sections"][0]
        assert sec["domain"] == "ai_solutions"
        assert sec["confidence"] == 0.9
        assert sec["escalated_to_cloud"] is True

    @pytest.mark.asyncio
    async def test_tier1b_keeps_local_if_cloud_has_lower_confidence(self):
        """Cloud result is worse than local → local result kept."""
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(
            side_effect=[
                _json_result(domain="dev_tooling", confidence=0.5),   # local
                _json_result(domain="not_relevant", confidence=0.3),   # cloud: lower
            ]
        )

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=[SAMPLE_SECTION]),
                _make_config(session=session, llm_client=llm),
            )

        sec = result["classified_sections"][0]
        assert sec["domain"] == "dev_tooling"
        assert sec["escalated_to_cloud"] is False

    @pytest.mark.asyncio
    async def test_multiple_sections_all_classified(self):
        session = _make_session()
        sections = [
            {**SAMPLE_SECTION, "section_index": 0},
            {"section_index": 1, "content": "AI discussion", "start_timestamp": "5:01", "end_timestamp": "10:00"},
        ]
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_result())

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=sections),
                _make_config(session=session, llm_client=llm),
            )

        assert len(result["classified_sections"]) == 2

    @pytest.mark.asyncio
    async def test_prompt_version_recorded(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_result())

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=[SAMPLE_SECTION]),
                _make_config(session=session, llm_client=llm),
            )

        assert result["prompt_versions"]["classify"] == "cls_hash_001"

    @pytest.mark.asyncio
    async def test_db_update_called_per_section(self):
        session = _make_session()
        sections = [
            {**SAMPLE_SECTION, "section_index": 0},
            {"section_index": 1, "content": "More content", "start_timestamp": "5:01", "end_timestamp": "10:00"},
        ]
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_result())

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await classify_node(
                _base_state(sections=sections),
                _make_config(session=session, llm_client=llm),
            )

        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_empty_sections_skips_llm(self):
        session = _make_session()
        llm = AsyncMock()

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=[]),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_not_awaited()
        assert result["classified_sections"] == []

    @pytest.mark.asyncio
    async def test_no_errors_on_success(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_result())

        with patch("app.pipeline.nodes.classify.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await classify_node(
                _base_state(sections=[SAMPLE_SECTION]),
                _make_config(session=session, llm_client=llm),
            )

        assert result["errors"] == []
