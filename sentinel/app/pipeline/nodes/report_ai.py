"""Report node — AI Solutions & Implementation domain."""
from langchain_core.runnables import RunnableConfig

from app.pipeline.nodes._report_base import generate_domain_report
from app.pipeline.state import PipelineState
from app.services.llm_client import LLMClient


async def report_ai_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Generate AI Solutions report for ai_solutions-classified sections."""
    cfg = config.get("configurable", {})
    session = cfg["session"]
    llm_client: LLMClient = cfg.get("llm_client") or LLMClient()
    return await generate_domain_report(state, session, llm_client, "ai_solutions", "report_ai")
