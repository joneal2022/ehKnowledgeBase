"""Persist node — marks pipeline completion on Source record."""
from langchain_core.runnables import RunnableConfig
from sqlalchemy import update

from app.models.source import ProcessingStatus, Source
from app.pipeline.state import PipelineState


async def persist_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Set Source.processing_status = completed; flush session.

    All domain errors have accumulated in state["errors"] throughout the pipeline.
    This node marks completion regardless — partial results are still persisted.

    Returns state updates:
      errors (empty — completion errors not surfaced here)
    """
    cfg = config.get("configurable", {})
    session = cfg["session"]

    await session.execute(
        update(Source)
        .where(Source.id == state["source_id"])
        .values(processing_status=ProcessingStatus.completed)
    )
    await session.flush()

    return {"errors": []}
