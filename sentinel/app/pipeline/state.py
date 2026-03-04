"""LangGraph pipeline state — the single TypedDict threaded through every node.

Design notes:
- `errors` uses Annotated[list, operator.add] so each node can append errors
  without overwriting prior errors (LangGraph merges them).
- All other fields use plain types (last-write wins), which is correct since
  each stage fully replaces its output field.
- `prompt_versions` accumulates task→hash pairs for recording in the job metadata.
"""
import operator
from typing import Annotated, TypedDict


class PipelineState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    source_id: str       # UUID string of the Source record
    url: str             # YouTube URL being processed

    # ── Stage outputs (each node writes its own slice) ─────────────────────────
    transcript: str                   # raw transcript from YouTube
    original_title: str | None        # raw YouTube title (stored as original_title)
    author: str | None                # channel / author name

    preprocessed_transcript: str      # after local-7B caption cleanup

    sections: list[dict]              # [{section_index, content, start_timestamp, end_timestamp}]
    classified_sections: list[dict]   # sections + {domain, confidence, reasoning, needs_review, escalated_to_cloud}

    reports: dict[str, dict]          # domain → {title, summary, key_takeaways, action_items,
                                      #            relevance_score, model_used, prompt_version}
    synthesis: dict                   # {title, tldr, dont_miss, domain_breakdown}

    # ── Cross-cutting ──────────────────────────────────────────────────────────
    errors: Annotated[list[str], operator.add]   # accumulated across nodes
    prompt_versions: dict[str, str]              # task_name → version_hash
