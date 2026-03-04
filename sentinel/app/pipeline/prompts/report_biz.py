"""Business Development & Growth report prompt — cloud model."""

BUSINESS_CONTEXT = """
You are generating insights for the owner of a custom software development company
based in Louisiana with clients in Dallas and Houston. The company has 15 developers
(mostly in India) and is transitioning to also offer AI solutions alongside traditional
custom software. The owner needs actionable intelligence, not academic summaries.

When analyzing content, always consider:
- How does this apply to winning more clients in the Dallas/Houston market?
- What's the revenue or growth opportunity?
- What specific actions could the owner take this week/month?
- Is this scalable for a 15-dev team?
"""

PROMPT_TEMPLATE = (
    BUSINESS_CONTEXT
    + """

You are generating an executive report for the BUSINESS DEVELOPMENT & GROWTH domain.
This covers: client acquisition, sales processes, pricing strategies, ROI methodology,
case studies, marketing positioning, hot verticals, and pipeline management for a
custom software + AI solutions company.

{few_shot_examples}

TRANSCRIPT SECTIONS CLASSIFIED AS BUSINESS_DEV:
{sections_text}

Generate a structured executive report. Respond with ONLY a JSON object:
{{
  "title": "<concise report title describing what business development topics were covered>",
  "summary": "<2-3 sentence executive summary of the key business growth insights>",
  "key_takeaways": [
    "<specific, actionable takeaway 1>",
    "<specific, actionable takeaway 2>",
    "<specific, actionable takeaway 3>"
  ],
  "action_items": [
    "<concrete action item with owner and timeframe>",
    "<concrete action item with owner and timeframe>"
  ],
  "relevance_score": <0.0-1.0 — how relevant is this to growing a custom software + AI business>,
  "business_application": "<1-2 sentences: what specific business development move should the owner make based on this?>"
}}
"""
)
