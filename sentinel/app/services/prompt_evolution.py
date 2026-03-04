"""Prompt evolution service — Tier 2 feedback loop.

Accumulates human corrections into the few_shot_bank.
When enough examples accumulate, auto-rebuilds the prompt with injected few-shot examples.
"""
import hashlib
import importlib
import json
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.few_shot import FewShotExample
from app.models.prompt_version import PromptVersion


class PromptEvolutionService:
    REBUILD_THRESHOLD = 5
    MAX_FEW_SHOT_EXAMPLES = 5

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def process_classification_correction(
        self,
        section_content: str,
        original_domain: str,
        correct_domain: str,
        feedback_id=None,
    ) -> None:
        """Store a classification correction; rebuild prompt if threshold reached."""
        example = FewShotExample(
            task_type="classify",
            input_text=section_content[:500],
            original_output={"domain": original_domain},
            corrected_output={"domain": correct_domain},
            source_feedback_id=feedback_id,
        )
        self._session.add(example)
        await self._session.flush()

        count = await self._count_active_examples("classify")
        if count >= self.REBUILD_THRESHOLD:
            await self._rebuild_prompt("classify")

    async def process_title_correction(
        self,
        old_title: str,
        new_title: str,
        context: str = "",
        feedback_id=None,
    ) -> None:
        """Store a title correction as a few-shot example."""
        example = FewShotExample(
            task_type="title",
            input_text=context or old_title,
            original_output={"title": old_title},
            corrected_output={"title": new_title},
            source_feedback_id=feedback_id,
        )
        self._session.add(example)
        await self._session.flush()

    async def process_report_rating(
        self,
        report_id,
        rating: int,
        feedback_id=None,
    ) -> None:
        """Record a report rating. Feedback row is already created by the API.

        Future: track avg rating per model×domain for quality dashboard.
        """
        pass  # Aggregation happens at query time from the feedback table

    async def _count_active_examples(self, task_type: str) -> int:
        result = await self._session.execute(
            select(func.count(FewShotExample.id))
            .where(FewShotExample.task_type == task_type)
            .where(FewShotExample.is_active == True)  # noqa: E712
        )
        return result.scalar() or 0

    async def _rebuild_prompt(self, task_type: str) -> None:
        """Rebuild the active prompt for task_type with current few-shot examples."""
        result = await self._session.execute(
            select(FewShotExample)
            .where(FewShotExample.task_type == task_type)
            .where(FewShotExample.is_active == True)  # noqa: E712
            .order_by(FewShotExample.created_at.desc())
            .limit(self.MAX_FEW_SHOT_EXAMPLES)
        )
        examples = result.scalars().all()

        # Build few-shot block to inject
        few_shot_block = "Here are examples of correct classifications:\n\n"
        for ex in examples:
            excerpt = ex.input_text[:200]
            few_shot_block += f'Section excerpt: "{excerpt}..."\n'
            few_shot_block += f"Correct classification: {json.dumps(ex.corrected_output)}\n\n"

        # Load base prompt template
        module = importlib.import_module(f"app.pipeline.prompts.{task_type}")
        base_prompt = module.PROMPT_TEMPLATE
        new_content = base_prompt.replace("{few_shot_examples}", few_shot_block)

        version_hash = hashlib.sha256(new_content.encode()).hexdigest()[:12]

        # Deactivate current active version
        await self._session.execute(
            update(PromptVersion)
            .where(PromptVersion.prompt_name == task_type)
            .where(PromptVersion.is_active == True)  # noqa: E712
            .values(is_active=False)
        )

        # Save new version
        new_version = PromptVersion(
            prompt_name=task_type,
            version_hash=version_hash,
            content=new_content,
            few_shot_examples=[
                {"input": ex.input_text, "output": ex.corrected_output}
                for ex in examples
            ],
            is_active=True,
            activated_at=datetime.now(timezone.utc),
        )
        self._session.add(new_version)
        await self._session.flush()
