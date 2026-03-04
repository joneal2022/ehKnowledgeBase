"""LangGraph pipeline graph — build_graph() returns a compiled StateGraph.

Task 9: graph shell with stub nodes.
Tasks 10-14 replace stubs with real implementations by updating build_graph().

Node execution order:
  START → extract → preprocess → segment → classify
        → report_dev → report_ai → report_biz
        → synthesize → persist → END
"""
from langgraph.graph import END, START, StateGraph

from app.pipeline.state import PipelineState

_compiled = None


# ── Stub nodes (replaced task-by-task in Tasks 10-14) ──────────────────────────

async def _stub(state: PipelineState) -> dict:
    """Placeholder — returns empty dict (no state changes)."""
    return {}


def build_graph():
    """Construct and compile the Sentinel LangGraph pipeline."""
    from app.pipeline.nodes import (
        classify,
        extract,
        persist,
        preprocess,
        report_ai,
        report_biz,
        report_dev,
        segment,
        synthesize,
    )

    g = StateGraph(PipelineState)

    g.add_node("extract", extract.extract_node)
    g.add_node("preprocess", preprocess.preprocess_node)
    g.add_node("segment", segment.segment_node)
    g.add_node("classify", classify.classify_node)
    g.add_node("report_dev", report_dev.report_dev_node)
    g.add_node("report_ai", report_ai.report_ai_node)
    g.add_node("report_biz", report_biz.report_biz_node)
    g.add_node("synthesize", synthesize.synthesize_node)
    g.add_node("persist", persist.persist_node)

    g.add_edge(START, "extract")
    g.add_edge("extract", "preprocess")
    g.add_edge("preprocess", "segment")
    g.add_edge("segment", "classify")
    g.add_edge("classify", "report_dev")
    g.add_edge("report_dev", "report_ai")
    g.add_edge("report_ai", "report_biz")
    g.add_edge("report_biz", "synthesize")
    g.add_edge("synthesize", "persist")
    g.add_edge("persist", END)

    return g.compile()


def get_compiled_graph():
    """Return the singleton compiled graph (built once on first call)."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled
