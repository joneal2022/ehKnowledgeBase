"""Unit tests for report_dev_node, report_ai_node, report_biz_node — Task 13."""
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.nodes.report_dev import report_dev_node
from app.pipeline.nodes.report_ai import report_ai_node
from app.pipeline.nodes.report_biz import report_biz_node
from app.pipeline.state import PipelineState


# ── Helpers ──────────────────────────────────────────────────────────────────

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
    session.add = MagicMock()   # add() is sync in SQLAlchemy
    session.flush = AsyncMock()
    return session


def _make_config(session=None, llm_client=None):
    return {"configurable": {"session": session or _make_session(), "llm_client": llm_client}}


def _make_prompt_manager(hash_val="rpt_hash_001"):
    mgr = AsyncMock()
    mgr.get_active_prompt = AsyncMock(
        return_value="{sections_text}\n{few_shot_examples}"
    )
    mgr.get_prompt_version_hash = AsyncMock(return_value=hash_val)
    return mgr


def _json_report(title="Test Report", summary="Summary text"):
    return json.dumps({
        "title": title,
        "summary": summary,
        "key_takeaways": ["takeaway 1", "takeaway 2"],
        "action_items": ["action 1"],
        "relevance_score": 0.85,
    })


def _section(domain: str, idx: int = 0) -> dict:
    return {
        "section_index": idx,
        "content": f"Content about {domain}",
        "domain": domain,
        "confidence": 0.9,
    }


# ── report_dev_node ───────────────────────────────────────────────────────────

class TestReportDevNode:
    @pytest.mark.asyncio
    async def test_no_dev_sections_skips_llm(self):
        session = _make_session()
        llm = AsyncMock()
        sections = [_section("ai_solutions"), _section("business_dev")]

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await report_dev_node(
                _base_state(classified_sections=sections),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_not_called()
        assert result["reports"] == {}

    @pytest.mark.asyncio
    async def test_dev_sections_calls_llm_with_report_task(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_report())

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await report_dev_node(
                _base_state(classified_sections=[_section("dev_tooling")]),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_awaited_once()
        assert llm.complete.call_args[0][0] == "report"

    @pytest.mark.asyncio
    async def test_br2_model_used_and_prompt_version_stored(self):
        """BR-2: Report row must have model_used and prompt_version."""
        session = _make_session()
        added = []
        session.add = MagicMock(side_effect=added.append)
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_report())

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager("rpt_hash_001")
            await report_dev_node(
                _base_state(classified_sections=[_section("dev_tooling")]),
                _make_config(session=session, llm_client=llm),
            )

        assert len(added) == 1
        row = added[0]
        assert row.model_used is not None
        assert row.prompt_version == "rpt_hash_001"

    @pytest.mark.asyncio
    async def test_tc1_model_used_from_settings_not_hardcoded(self):
        """TC-1: model_used must come from settings.get_model_for_task('report')."""
        session = _make_session()
        added = []
        session.add = MagicMock(side_effect=added.append)
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_report())

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            with patch("app.pipeline.nodes._report_base.settings") as mock_settings:
                mock_settings.get_model_for_task.return_value = "test-model-from-config"
                await report_dev_node(
                    _base_state(classified_sections=[_section("dev_tooling")]),
                    _make_config(session=session, llm_client=llm),
                )

        mock_settings.get_model_for_task.assert_called_with("report")
        assert added[0].model_used == "test-model-from-config"

    @pytest.mark.asyncio
    async def test_report_stored_in_db(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_report())

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await report_dev_node(
                _base_state(classified_sections=[_section("dev_tooling")]),
                _make_config(session=session, llm_client=llm),
            )

        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_failure_returns_error_no_db_write(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="not valid json!!!")

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await report_dev_node(
                _base_state(classified_sections=[_section("dev_tooling")]),
                _make_config(session=session, llm_client=llm),
            )

        session.add.assert_not_called()
        assert len(result["errors"]) == 1
        assert "report_dev_tooling:" in result["errors"][0]


# ── report_ai_node ────────────────────────────────────────────────────────────

class TestReportAiNode:
    @pytest.mark.asyncio
    async def test_no_ai_sections_skips_llm(self):
        session = _make_session()
        llm = AsyncMock()

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await report_ai_node(
                _base_state(classified_sections=[_section("dev_tooling")]),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_not_called()
        assert result["reports"] == {}

    @pytest.mark.asyncio
    async def test_ai_sections_produces_report(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_report(title="AI Report"))

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await report_ai_node(
                _base_state(classified_sections=[_section("ai_solutions")]),
                _make_config(session=session, llm_client=llm),
            )

        assert "ai_solutions" in result["reports"]
        assert result["reports"]["ai_solutions"]["title"] == "AI Report"

    @pytest.mark.asyncio
    async def test_br2_model_used_set_on_report(self):
        session = _make_session()
        added = []
        session.add = MagicMock(side_effect=added.append)
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_report())

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await report_ai_node(
                _base_state(classified_sections=[_section("ai_solutions")]),
                _make_config(session=session, llm_client=llm),
            )

        assert added[0].model_used is not None
        assert added[0].prompt_version is not None


# ── report_biz_node ───────────────────────────────────────────────────────────

class TestReportBizNode:
    @pytest.mark.asyncio
    async def test_no_biz_sections_skips_llm(self):
        session = _make_session()
        llm = AsyncMock()

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await report_biz_node(
                _base_state(classified_sections=[_section("dev_tooling")]),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_not_called()
        assert result["reports"] == {}

    @pytest.mark.asyncio
    async def test_biz_sections_produces_report(self):
        session = _make_session()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_report(title="Biz Report"))

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            result = await report_biz_node(
                _base_state(classified_sections=[_section("business_dev")]),
                _make_config(session=session, llm_client=llm),
            )

        assert "business_dev" in result["reports"]

    @pytest.mark.asyncio
    async def test_br2_model_used_set_on_report(self):
        session = _make_session()
        added = []
        session.add = MagicMock(side_effect=added.append)
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=_json_report())

        with patch("app.pipeline.nodes._report_base.PromptManager") as MockPM:
            MockPM.return_value = _make_prompt_manager()
            await report_biz_node(
                _base_state(classified_sections=[_section("business_dev")]),
                _make_config(session=session, llm_client=llm),
            )

        assert added[0].model_used is not None
        assert added[0].prompt_version is not None
