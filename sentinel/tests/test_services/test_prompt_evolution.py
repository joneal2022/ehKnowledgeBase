"""Unit tests for PromptEvolutionService — Task 17."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch

from app.models.few_shot import FewShotExample
from app.models.prompt_version import PromptVersion
from app.services.prompt_evolution import PromptEvolutionService


def _make_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_scalar_result(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _make_scalars_result(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


class TestProcessClassificationCorrection:
    @pytest.mark.asyncio
    async def test_adds_few_shot_example_to_db(self):
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalar_result(1))  # count = 1, below threshold
        added = []
        session.add = MagicMock(side_effect=added.append)

        svc = PromptEvolutionService(session)
        await svc.process_classification_correction(
            section_content="How to set up CI/CD pipelines with GitHub Actions.",
            original_domain="ai_solutions",
            correct_domain="dev_tooling",
        )

        few_shot_rows = [o for o in added if isinstance(o, FewShotExample)]
        assert len(few_shot_rows) == 1
        row = few_shot_rows[0]
        assert row.task_type == "classify"
        assert row.corrected_output == {"domain": "dev_tooling"}
        assert row.original_output == {"domain": "ai_solutions"}

    @pytest.mark.asyncio
    async def test_input_text_truncated_to_500_chars(self):
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalar_result(1))
        added = []
        session.add = MagicMock(side_effect=added.append)

        long_content = "x" * 1000
        svc = PromptEvolutionService(session)
        await svc.process_classification_correction(
            section_content=long_content,
            original_domain="dev_tooling",
            correct_domain="ai_solutions",
        )

        row = next(o for o in added if isinstance(o, FewShotExample))
        assert len(row.input_text) == 500

    @pytest.mark.asyncio
    async def test_no_rebuild_below_threshold(self):
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalar_result(3))  # count = 3 < 5

        svc = PromptEvolutionService(session)
        with patch.object(svc, "_rebuild_prompt") as mock_rebuild:
            await svc.process_classification_correction(
                section_content="content",
                original_domain="dev_tooling",
                correct_domain="ai_solutions",
            )

        mock_rebuild.assert_not_called()

    @pytest.mark.asyncio
    async def test_rebuild_triggered_at_threshold(self):
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalar_result(5))  # count = 5 = threshold

        svc = PromptEvolutionService(session)
        with patch.object(svc, "_rebuild_prompt", new_callable=AsyncMock) as mock_rebuild:
            await svc.process_classification_correction(
                section_content="content",
                original_domain="dev_tooling",
                correct_domain="ai_solutions",
            )

        mock_rebuild.assert_awaited_once_with("classify")

    @pytest.mark.asyncio
    async def test_attaches_feedback_id_when_provided(self):
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalar_result(1))
        added = []
        session.add = MagicMock(side_effect=added.append)
        feedback_id = uuid.uuid4()

        svc = PromptEvolutionService(session)
        await svc.process_classification_correction(
            section_content="content",
            original_domain="dev_tooling",
            correct_domain="ai_solutions",
            feedback_id=feedback_id,
        )

        row = next(o for o in added if isinstance(o, FewShotExample))
        assert row.source_feedback_id == feedback_id


class TestProcessTitleCorrection:
    @pytest.mark.asyncio
    async def test_adds_title_few_shot_example(self):
        session = _make_session()
        added = []
        session.add = MagicMock(side_effect=added.append)

        svc = PromptEvolutionService(session)
        await svc.process_title_correction(
            old_title="Live Recording Jan 15",
            new_title="RAG Architecture + AI Pricing Strategies",
        )

        few_shot_rows = [o for o in added if isinstance(o, FewShotExample)]
        assert len(few_shot_rows) == 1
        row = few_shot_rows[0]
        assert row.task_type == "title"
        assert row.corrected_output == {"title": "RAG Architecture + AI Pricing Strategies"}
        assert row.original_output == {"title": "Live Recording Jan 15"}

    @pytest.mark.asyncio
    async def test_flushes_session(self):
        session = _make_session()
        svc = PromptEvolutionService(session)
        await svc.process_title_correction(
            old_title="old",
            new_title="new",
        )
        session.flush.assert_awaited()


class TestRebuildPrompt:
    @pytest.mark.asyncio
    async def test_creates_new_prompt_version_with_few_shots(self):
        session = _make_session()

        examples = [
            MagicMock(
                input_text="CI/CD pipelines discussion",
                corrected_output={"domain": "dev_tooling"},
                created_at=MagicMock(),
            ),
            MagicMock(
                input_text="RAG implementation approach",
                corrected_output={"domain": "ai_solutions"},
                created_at=MagicMock(),
            ),
        ]
        session.execute = AsyncMock(return_value=_make_scalars_result(examples))
        added = []
        session.add = MagicMock(side_effect=added.append)

        svc = PromptEvolutionService(session)
        await svc._rebuild_prompt("classify")

        prompt_versions = [o for o in added if isinstance(o, PromptVersion)]
        assert len(prompt_versions) == 1
        pv = prompt_versions[0]
        assert pv.prompt_name == "classify"
        assert pv.is_active is True
        assert pv.activated_at is not None
        assert pv.few_shot_examples is not None
        assert len(pv.few_shot_examples) == 2

    @pytest.mark.asyncio
    async def test_new_version_content_contains_few_shot_block(self):
        session = _make_session()

        examples = [
            MagicMock(
                input_text="Setting up Docker for local dev",
                corrected_output={"domain": "dev_tooling"},
                created_at=MagicMock(),
            ),
        ]
        session.execute = AsyncMock(return_value=_make_scalars_result(examples))
        added = []
        session.add = MagicMock(side_effect=added.append)

        svc = PromptEvolutionService(session)
        await svc._rebuild_prompt("classify")

        pv = next(o for o in added if isinstance(o, PromptVersion))
        assert "Setting up Docker" in pv.content
        assert "dev_tooling" in pv.content

    @pytest.mark.asyncio
    async def test_deactivates_old_active_version(self):
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalars_result([
            MagicMock(
                input_text="some content",
                corrected_output={"domain": "dev_tooling"},
                created_at=MagicMock(),
            )
        ]))

        svc = PromptEvolutionService(session)
        await svc._rebuild_prompt("classify")

        # execute should be called: once for the UPDATE (deactivate old), once for the SELECT
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_version_hash_is_12_chars(self):
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalars_result([
            MagicMock(
                input_text="content",
                corrected_output={"domain": "ai_solutions"},
                created_at=MagicMock(),
            )
        ]))
        added = []
        session.add = MagicMock(side_effect=added.append)

        svc = PromptEvolutionService(session)
        await svc._rebuild_prompt("classify")

        pv = next(o for o in added if isinstance(o, PromptVersion))
        assert len(pv.version_hash) == 12
