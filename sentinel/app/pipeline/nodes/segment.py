"""Segment node — splits preprocessed transcript into topical sections (cloud LLM)."""
from langchain_core.runnables import RunnableConfig

from app.models.section import ContentSection
from app.pipeline.prompts.manager import PromptManager
from app.pipeline.state import PipelineState
from app.services.llm_client import LLMClient, parse_llm_json


async def segment_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Call cloud LLM to split transcript into sections; persist to DB.

    Returns state updates:
      sections, prompt_versions, errors
    """
    cfg = config.get("configurable", {})
    session = cfg["session"]
    llm_client: LLMClient = cfg.get("llm_client") or LLMClient()

    transcript = state.get("preprocessed_transcript") or state.get("transcript", "")
    if not transcript:
        return {"sections": [], "prompt_versions": {}, "errors": []}

    prompt_manager = PromptManager(session)
    prompt_template = await prompt_manager.get_active_prompt("segment")
    version_hash = await prompt_manager.get_prompt_version_hash("segment")

    prompt = prompt_template.format(transcript=transcript, few_shot_examples="")

    try:
        raw = await llm_client.complete("segment", prompt)
        sections_data = parse_llm_json(raw)
        # segment returns a JSON array, not object
        if isinstance(sections_data, list):
            sections = sections_data
        else:
            sections = sections_data.get("sections", [])
    except Exception as exc:
        return {
            "sections": [],
            "prompt_versions": {"segment": version_hash},
            "errors": [f"segment: failed to parse sections — {exc}"],
        }

    # Persist ContentSection rows
    source_id = state["source_id"]
    for sec in sections:
        row = ContentSection(
            source_id=source_id,
            section_index=sec.get("section_index", 0),
            content=sec.get("content", ""),
            start_timestamp=sec.get("start_timestamp"),
            end_timestamp=sec.get("end_timestamp"),
        )
        session.add(row)
    await session.flush()

    return {
        "sections": sections,
        "prompt_versions": {"segment": version_hash},
        "errors": [],
    }
