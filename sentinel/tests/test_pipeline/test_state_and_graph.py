"""Unit tests for PipelineState and graph shell — Task 9."""
import operator
import pytest

from app.pipeline.state import PipelineState
from app.pipeline.graph import build_graph


# ── PipelineState TypedDict structure ─────────────────────────────────────────

class TestPipelineState:
    def test_state_can_be_constructed(self):
        state: PipelineState = {
            "source_id": "abc-123",
            "url": "https://www.youtube.com/watch?v=test",
            "transcript": "",
            "original_title": None,
            "author": None,
            "preprocessed_transcript": "",
            "sections": [],
            "classified_sections": [],
            "reports": {},
            "synthesis": {},
            "errors": [],
            "prompt_versions": {},
        }
        assert state["source_id"] == "abc-123"

    def test_state_has_source_id_field(self):
        assert "source_id" in PipelineState.__annotations__

    def test_state_has_url_field(self):
        assert "url" in PipelineState.__annotations__

    def test_state_has_transcript_fields(self):
        annotations = PipelineState.__annotations__
        assert "transcript" in annotations
        assert "preprocessed_transcript" in annotations

    def test_state_has_pipeline_output_fields(self):
        annotations = PipelineState.__annotations__
        assert "sections" in annotations
        assert "classified_sections" in annotations
        assert "reports" in annotations
        assert "synthesis" in annotations

    def test_state_has_tracking_fields(self):
        annotations = PipelineState.__annotations__
        assert "errors" in annotations
        assert "prompt_versions" in annotations

    def test_errors_uses_list_reducer(self):
        """errors must be Annotated[list[str], operator.add] so nodes can accumulate."""
        import typing
        hint = PipelineState.__annotations__["errors"]
        # Annotated type has __metadata__ with the reducer
        args = typing.get_args(hint)
        assert len(args) == 2, "errors should be Annotated[list[str], operator.add]"
        assert args[1] is operator.add

    def test_errors_accumulate_across_updates(self):
        """Verify the reducer works: two error lists are concatenated, not replaced."""
        existing = ["error_1"]
        new = ["error_2"]
        merged = operator.add(existing, new)
        assert merged == ["error_1", "error_2"]


# ── Graph structure ────────────────────────────────────────────────────────────

class TestBuildGraph:
    def test_graph_compiles_without_error(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        graph = build_graph()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {
            "extract", "preprocess", "segment", "classify",
            "report_dev", "report_ai", "report_biz",
            "synthesize", "persist",
            "__start__", "__end__",
        }
        assert expected.issubset(node_names)

    def test_graph_has_nine_pipeline_nodes(self):
        graph = build_graph()
        # Exclude __start__ and __end__
        pipeline_nodes = {
            k for k in graph.get_graph().nodes.keys()
            if not k.startswith("__")
        }
        assert len(pipeline_nodes) == 9

    def test_get_compiled_graph_returns_same_instance(self):
        from app.pipeline import graph as graph_mod
        graph_mod._compiled = None  # reset singleton
        g1 = graph_mod.get_compiled_graph()
        g2 = graph_mod.get_compiled_graph()
        assert g1 is g2
        graph_mod._compiled = None  # cleanup
