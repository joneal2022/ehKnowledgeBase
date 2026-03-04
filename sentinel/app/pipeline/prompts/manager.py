"""Prompt manager — versioning, few-shot injection, first-use persistence.

Every pipeline node fetches prompts through PromptManager. It:
- Returns the active prompt version from the DB (if one exists for the task)
- On first use, saves the base template to prompt_versions and returns it
- Produces strict variants for Tier 1 parse-retry (Loop 1A)
- Provides the active version hash so pipeline nodes can record prompt_version on reports
"""
import hashlib
import importlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_version import PromptVersion

# Appended to any prompt for Tier 1 Loop 1A strict retry
STRICT_SUFFIX = """

CRITICAL: You MUST respond with ONLY a valid JSON object. No markdown, no backticks,
no explanation, no preamble. Just the JSON object starting with { and ending with }.
"""

# All known prompt task names
KNOWN_PROMPTS = frozenset({
    "preprocess",
    "segment",
    "classify",
    "report_dev",
    "report_ai",
    "report_biz",
    "synthesize",
})


class PromptManager:
    """Manages prompt versioning and few-shot injection for pipeline nodes.

    Usage:
        manager = PromptManager(session)
        prompt = await manager.get_active_prompt("classify")
        filled = prompt.format(section_content=..., few_shot_examples="")
        hash_ = await manager.get_prompt_version_hash("classify")
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_prompt(self, task_name: str) -> str:
        """Return active prompt content for task_name.

        Checks prompt_versions for an active version. If none exists,
        loads the base template from the prompt module, saves it to the
        DB (first-use persistence), and returns it.
        """
        version = await self._get_active_version(task_name)
        if version:
            return version.content

        # First use: load base, persist, return
        base = self._load_base_prompt(task_name)
        await self._save_base_prompt(task_name, base)
        return base

    async def get_prompt_version_hash(self, task_name: str) -> str:
        """Return the SHA256[:12] hash of the active prompt, or 'base' if none saved yet."""
        version = await self._get_active_version(task_name)
        return version.version_hash if version else "base"

    async def get_strict_variant(self, task_name: str) -> str:
        """Return the active prompt with STRICT_SUFFIX appended (Tier 1 Loop 1A retry)."""
        base = await self.get_active_prompt(task_name)
        return base + STRICT_SUFFIX

    # ── internal helpers ────────────────────────────────────────────────────────

    async def _get_active_version(self, task_name: str) -> PromptVersion | None:
        result = await self._session.execute(
            select(PromptVersion)
            .where(
                PromptVersion.prompt_name == task_name,
                PromptVersion.is_active.is_(True),
            )
            .order_by(PromptVersion.activated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _save_base_prompt(self, task_name: str, content: str) -> PromptVersion:
        """Persist a base prompt template to prompt_versions (first-use write)."""
        version_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        version = PromptVersion(
            prompt_name=task_name,
            version_hash=version_hash,
            content=content,
            is_active=True,
            activated_at=datetime.now(timezone.utc),
        )
        self._session.add(version)
        await self._session.flush()
        return version

    def _load_base_prompt(self, task_name: str) -> str:
        """Import the prompt module and return its PROMPT_TEMPLATE string.

        Raises ImportError if the module does not exist.
        """
        module = importlib.import_module(f"app.pipeline.prompts.{task_name}")
        return module.PROMPT_TEMPLATE
