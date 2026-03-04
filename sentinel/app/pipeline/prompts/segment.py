"""Transcript segmentation prompt — cloud model, topical section splitting."""

PROMPT_TEMPLATE = """You are segmenting a video transcript into distinct topical sections.

Each section should represent a single coherent topic or discussion point.
Target: 3-15 sections per hour of content (do not over-segment).

RULES:
- Each section must be self-contained and make sense on its own
- Preserve the original transcript text verbatim within each section
- Include approximate start timestamps where they appear in the transcript
- Sections should NOT overlap

{few_shot_examples}

TRANSCRIPT:
{transcript}

Respond with ONLY a JSON array:
[
  {{
    "section_index": 0,
    "start_timestamp": "<timestamp or null>",
    "end_timestamp": "<timestamp or null>",
    "content": "<verbatim transcript text for this section>"
  }},
  ...
]
"""
