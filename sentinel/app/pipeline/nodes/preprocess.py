"""Preprocess node — caption cleanup using local 7B model."""
from langchain_core.runnables import RunnableConfig

from app.pipeline.prompts.manager import PromptManager
from app.pipeline.state import PipelineState
from app.services.llm_client import LLMClient


async def preprocess_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Clean up auto-caption artifacts using the local 7B model.

    If transcript is empty (extract failed), returns immediately.
    If LLM call fails, falls back to raw transcript (graceful degradation).

    Returns state updates:
      preprocessed_transcript, prompt_versions, errors
    """
    cfg = config.get("configurable", {})
    session = cfg["session"]
    llm_client: LLMClient = cfg.get("llm_client") or LLMClient()

    transcript = state.get("transcript", "")
    if not transcript:
        return {
            "preprocessed_transcript": "",
            "prompt_versions": {},
            "errors": [],
        }

    prompt_manager = PromptManager(session)
    prompt_template = await prompt_manager.get_active_prompt("preprocess")
    version_hash = await prompt_manager.get_prompt_version_hash("preprocess")

    prompt = prompt_template.format(
        transcript=transcript,
        few_shot_examples="",
    )

    try:
        cleaned = await llm_client.complete("preprocess", prompt)
    except Exception as exc:
        # Graceful degradation: use raw transcript if LLM fails
        return {
            "preprocessed_transcript": transcript,
            "prompt_versions": {"preprocess": version_hash},
            "errors": [f"preprocess: LLM failed, using raw transcript — {exc}"],
        }

    return {
        "preprocessed_transcript": cleaned.strip() or transcript,
        "prompt_versions": {"preprocess": version_hash},
        "errors": [],
    }
