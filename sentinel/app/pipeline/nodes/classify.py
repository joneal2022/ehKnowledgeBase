"""Classify node — domain classification with Tier 1A retry and Tier 1B cloud escalation."""
from langchain_core.runnables import RunnableConfig
from sqlalchemy import update

from app.models.section import ContentSection, DomainEnum
from app.pipeline.prompts.manager import PromptManager
from app.pipeline.state import PipelineState
from app.services.llm_client import LLMClient, parse_llm_json

_CONFIDENCE_THRESHOLD = 0.6


async def _classify_one(
    section: dict,
    llm_client: LLMClient,
    prompt_manager: PromptManager,
    base_prompt: str,
) -> dict:
    """Classify one section. Implements Tier 1A (strict retry) and Tier 1B (cloud escalation)."""
    formatted = base_prompt.format(
        section_content=section.get("content", ""),
        few_shot_examples="",
    )

    # Attempt 1 — local model
    parsed = None
    try:
        raw = await llm_client.complete("classify", formatted)
        parsed = parse_llm_json(raw)
    except Exception:
        # Tier 1A — parse failure → retry with strict prompt variant
        try:
            strict = await prompt_manager.get_strict_variant("classify")
            strict_fmt = strict.format(
                section_content=section.get("content", ""),
                few_shot_examples="",
            )
            raw = await llm_client.complete("classify", strict_fmt)
            parsed = parse_llm_json(raw)
        except Exception as exc:
            return {
                **section,
                "domain": "not_relevant",
                "confidence": 0.0,
                "reasoning": f"Classification failed after retry: {exc}",
                "needs_review": True,
                "escalated_to_cloud": False,
            }

    # Tier 1B — low confidence → escalate to cloud
    escalated = False
    if parsed.get("confidence", 0) < _CONFIDENCE_THRESHOLD:
        try:
            cloud_raw = await llm_client.complete("classify_escalation", formatted)
            cloud_parsed = parse_llm_json(cloud_raw)
            if cloud_parsed.get("confidence", 0) > parsed.get("confidence", 0):
                parsed = cloud_parsed
                escalated = True
        except Exception:
            pass  # Keep local result if cloud fails

    confidence = parsed.get("confidence", 0.0)
    return {
        **section,
        "domain": parsed.get("domain", "not_relevant"),
        "confidence": confidence,
        "reasoning": parsed.get("reasoning", ""),
        "needs_review": confidence < _CONFIDENCE_THRESHOLD,
        "escalated_to_cloud": escalated,
    }


async def classify_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Classify each section into a domain; update DB rows.

    Returns state updates:
      classified_sections, prompt_versions, errors
    """
    cfg = config.get("configurable", {})
    session = cfg["session"]
    llm_client: LLMClient = cfg.get("llm_client") or LLMClient()

    sections = state.get("sections", [])
    if not sections:
        return {"classified_sections": [], "prompt_versions": {}, "errors": []}

    prompt_manager = PromptManager(session)
    base_prompt = await prompt_manager.get_active_prompt("classify")
    version_hash = await prompt_manager.get_prompt_version_hash("classify")

    classified_sections: list[dict] = []
    errors: list[str] = []

    for section in sections:
        try:
            classified = await _classify_one(section, llm_client, prompt_manager, base_prompt)
            classified_sections.append(classified)

            # Persist classification back to DB
            try:
                domain_val = DomainEnum(classified["domain"])
            except ValueError:
                domain_val = None

            await session.execute(
                update(ContentSection)
                .where(ContentSection.source_id == state["source_id"])
                .where(ContentSection.section_index == classified.get("section_index", 0))
                .values(
                    domain=domain_val,
                    classification_confidence=classified["confidence"],
                    classification_reasoning=classified["reasoning"],
                    needs_review=classified["needs_review"],
                    escalated_to_cloud=classified["escalated_to_cloud"],
                )
            )
        except Exception as exc:
            errors.append(f"classify: section {section.get('section_index', '?')} — {exc}")

    await session.flush()

    return {
        "classified_sections": classified_sections,
        "prompt_versions": {"classify": version_hash},
        "errors": errors,
    }
