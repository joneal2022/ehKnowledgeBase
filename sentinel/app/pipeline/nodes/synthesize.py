"""Synthesize node — executive summary + generated title (cloud LLM)."""
from langchain_core.runnables import RunnableConfig
from sqlalchemy import update

from app.models.source import Source
from app.pipeline.prompts.manager import PromptManager
from app.pipeline.state import PipelineState
from app.services.llm_client import LLMClient, parse_llm_json


async def synthesize_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Generate executive summary and descriptive title from all domain reports.

    Updates Source.title in DB (BR-1, DR-4: generated title only — never original_title).

    Returns state updates:
      synthesis, prompt_versions, errors
    """
    cfg = config.get("configurable", {})
    session = cfg["session"]
    llm_client: LLMClient = cfg.get("llm_client") or LLMClient()

    reports = state.get("reports", {})
    original_title = state.get("original_title") or ""

    # Build domain reports text for the prompt
    domain_parts: list[str] = []
    for domain, report in reports.items():
        title = report.get("title", "")
        summary = report.get("summary", "")
        domain_parts.append(f"[{domain.upper()}]\nTitle: {title}\nSummary: {summary}")
    domain_reports_text = "\n\n".join(domain_parts) if domain_parts else "(no domain reports available)"

    prompt_manager = PromptManager(session)
    prompt_template = await prompt_manager.get_active_prompt("synthesize")
    version_hash = await prompt_manager.get_prompt_version_hash("synthesize")

    prompt = prompt_template.format(
        original_title=original_title,
        domain_reports_text=domain_reports_text,
        few_shot_examples="",
    )

    try:
        raw = await llm_client.complete("synthesize", prompt)
        parsed = parse_llm_json(raw)
    except Exception as exc:
        return {
            "synthesis": {},
            "prompt_versions": {"synthesize": version_hash},
            "errors": [f"synthesize: failed to generate synthesis — {exc}"],
        }

    # Update Source.title with the generated title (BR-1, DR-4)
    generated_title = parsed.get("title")
    if generated_title:
        await session.execute(
            update(Source)
            .where(Source.id == state["source_id"])
            .values(title=generated_title)
        )

    return {
        "synthesis": parsed,
        "prompt_versions": {"synthesize": version_hash},
        "errors": [],
    }
