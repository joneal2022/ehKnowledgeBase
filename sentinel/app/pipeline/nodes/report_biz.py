"""Report node — Business Development & Growth domain."""
from langchain_core.runnables import RunnableConfig

from app.pipeline.nodes._report_base import generate_domain_report
from app.pipeline.state import PipelineState
from app.services.llm_client import LLMClient


async def report_biz_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Generate Business Dev report for business_dev-classified sections."""
    cfg = config.get("configurable", {})
    session = cfg["session"]
    llm_client: LLMClient = cfg.get("llm_client") or LLMClient()
    return await generate_domain_report(state, session, llm_client, "business_dev", "report_biz")
