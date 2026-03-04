"""Unit tests for PromptManager — Task 6."""
import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.pipeline.prompts.manager import (
    KNOWN_PROMPTS,
    STRICT_SUFFIX,
    PromptManager,
)
from app.models.prompt_version import PromptVersion


def _make_session(scalar_result=None):
    """Build a mock AsyncSession that returns scalar_result from execute()."""
    session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = scalar_result
    session.execute = AsyncMock(return_value=exec_result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_version(task_name: str, content: str, version_hash: str = "abc123def456") -> PromptVersion:
    v = MagicMock(spec=PromptVersion)
    v.prompt_name = task_name
    v.content = content
    v.version_hash = version_hash
    v.is_active = True
    return v


# ── Prompt files — TC-5 (all 7 exist with {few_shot_examples}) ─────────────────

class TestPromptFiles:
    @pytest.mark.parametrize("task_name", [
        "preprocess", "segment", "classify",
        "report_dev", "report_ai", "report_biz", "synthesize",
    ])
    def test_prompt_module_has_prompt_template(self, task_name):
        import importlib
        mod = importlib.import_module(f"app.pipeline.prompts.{task_name}")
        assert hasattr(mod, "PROMPT_TEMPLATE"), f"{task_name} missing PROMPT_TEMPLATE"

    @pytest.mark.parametrize("task_name", [
        "preprocess", "segment", "classify",
        "report_dev", "report_ai", "report_biz", "synthesize",
    ])
    def test_prompt_template_has_few_shot_placeholder(self, task_name):
        """TC-5: every prompt must have {few_shot_examples} placeholder."""
        import importlib
        mod = importlib.import_module(f"app.pipeline.prompts.{task_name}")
        assert "{few_shot_examples}" in mod.PROMPT_TEMPLATE, (
            f"{task_name}.PROMPT_TEMPLATE is missing {{few_shot_examples}} placeholder"
        )

    @pytest.mark.parametrize("task_name", [
        "preprocess", "segment", "classify",
        "report_dev", "report_ai", "report_biz", "synthesize",
    ])
    def test_prompt_template_is_nonempty_string(self, task_name):
        import importlib
        mod = importlib.import_module(f"app.pipeline.prompts.{task_name}")
        assert isinstance(mod.PROMPT_TEMPLATE, str)
        assert len(mod.PROMPT_TEMPLATE.strip()) > 50

    def test_known_prompts_set_contains_all_seven(self):
        expected = {"preprocess", "segment", "classify", "report_dev", "report_ai", "report_biz", "synthesize"}
        assert expected == KNOWN_PROMPTS


# ── get_active_prompt ──────────────────────────────────────────────────────────

class TestGetActivePrompt:
    @pytest.mark.asyncio
    async def test_returns_db_version_content_when_active_exists(self):
        content = "DB version content"
        version = _make_version("classify", content, "abc123def456")
        session = _make_session(scalar_result=version)
        manager = PromptManager(session)

        result = await manager.get_active_prompt("classify")

        assert result == content

    @pytest.mark.asyncio
    async def test_returns_base_template_when_no_db_version(self):
        session = _make_session(scalar_result=None)
        manager = PromptManager(session)

        result = await manager.get_active_prompt("classify")

        import app.pipeline.prompts.classify as mod
        assert result == mod.PROMPT_TEMPLATE

    @pytest.mark.asyncio
    async def test_saves_to_db_on_first_use(self):
        session = _make_session(scalar_result=None)
        manager = PromptManager(session)

        await manager.get_active_prompt("classify")

        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_save_when_db_version_exists(self):
        version = _make_version("classify", "existing content")
        session = _make_session(scalar_result=version)
        manager = PromptManager(session)

        await manager.get_active_prompt("classify")

        session.add.assert_not_called()
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_task_raises_import_error(self):
        session = _make_session(scalar_result=None)
        manager = PromptManager(session)

        with pytest.raises((ImportError, ModuleNotFoundError)):
            await manager.get_active_prompt("nonexistent_task_xyz")


# ── get_prompt_version_hash ────────────────────────────────────────────────────

class TestGetPromptVersionHash:
    @pytest.mark.asyncio
    async def test_returns_version_hash_from_db(self):
        version = _make_version("classify", "content", "deadbeef1234")
        session = _make_session(scalar_result=version)
        manager = PromptManager(session)

        result = await manager.get_prompt_version_hash("classify")

        assert result == "deadbeef1234"

    @pytest.mark.asyncio
    async def test_returns_base_when_no_db_version(self):
        session = _make_session(scalar_result=None)
        manager = PromptManager(session)

        result = await manager.get_prompt_version_hash("classify")

        assert result == "base"


# ── get_strict_variant ─────────────────────────────────────────────────────────

class TestGetStrictVariant:
    @pytest.mark.asyncio
    async def test_strict_variant_appends_strict_suffix(self):
        content = "base prompt content"
        version = _make_version("classify", content)
        session = _make_session(scalar_result=version)
        manager = PromptManager(session)

        result = await manager.get_strict_variant("classify")

        assert result == content + STRICT_SUFFIX

    @pytest.mark.asyncio
    async def test_strict_suffix_contains_json_instruction(self):
        assert "JSON" in STRICT_SUFFIX
        assert "{" in STRICT_SUFFIX


# ── _save_base_prompt — SHA256 hash ──────────────────────────────────────────

class TestSaveBasePrompt:
    @pytest.mark.asyncio
    async def test_saved_version_has_sha256_12char_hash(self):
        session = _make_session(scalar_result=None)
        manager = PromptManager(session)

        content = "some prompt content"
        await manager._save_base_prompt("classify", content)

        added = session.add.call_args[0][0]
        expected_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        assert added.version_hash == expected_hash

    @pytest.mark.asyncio
    async def test_saved_version_has_correct_task_name(self):
        session = _make_session(scalar_result=None)
        manager = PromptManager(session)

        await manager._save_base_prompt("segment", "content")

        added = session.add.call_args[0][0]
        assert added.prompt_name == "segment"

    @pytest.mark.asyncio
    async def test_saved_version_is_active(self):
        session = _make_session(scalar_result=None)
        manager = PromptManager(session)

        await manager._save_base_prompt("classify", "content")

        added = session.add.call_args[0][0]
        assert added.is_active is True

    @pytest.mark.asyncio
    async def test_saved_version_has_activated_at(self):
        session = _make_session(scalar_result=None)
        manager = PromptManager(session)

        await manager._save_base_prompt("classify", "content")

        added = session.add.call_args[0][0]
        assert added.activated_at is not None


# ── _load_base_prompt ─────────────────────────────────────────────────────────

class TestLoadBasePrompt:
    def test_loads_classify_prompt(self):
        session = _make_session()
        manager = PromptManager(session)
        result = manager._load_base_prompt("classify")
        import app.pipeline.prompts.classify as mod
        assert result == mod.PROMPT_TEMPLATE

    def test_loads_synthesize_prompt(self):
        session = _make_session()
        manager = PromptManager(session)
        result = manager._load_base_prompt("synthesize")
        import app.pipeline.prompts.synthesize as mod
        assert result == mod.PROMPT_TEMPLATE

    def test_unknown_task_raises_import_error(self):
        session = _make_session()
        manager = PromptManager(session)
        with pytest.raises((ImportError, ModuleNotFoundError)):
            manager._load_base_prompt("does_not_exist_xyz")
