"""Development Process & Tooling report prompt — cloud model."""

BUSINESS_CONTEXT = """
You are generating insights for the owner of a custom software development company
based in Louisiana with clients in Dallas and Houston. The company has 15 developers
(mostly in India) and is transitioning to also offer AI solutions alongside traditional
custom software. The owner needs actionable intelligence, not academic summaries.

When analyzing content, always consider:
- How does this apply to a 15-dev custom software shop?
- What's the productivity or workflow improvement opportunity here?
- What would it take to implement this? (people, time, cost)
- Is this relevant NOW or is it future speculation?
"""

PROMPT_TEMPLATE = (
    BUSINESS_CONTEXT
    + """

You are generating an executive report for the DEVELOPMENT PROCESS & TOOLING domain.
This covers: AI-assisted development tools, IDE improvements, frameworks, deployment workflows,
code quality practices, testing strategies, and team productivity for a software development company.

{few_shot_examples}

TRANSCRIPT SECTIONS CLASSIFIED AS DEV_TOOLING:
{sections_text}

Generate a structured executive report. Respond with ONLY a JSON object:
{{
  "title": "<concise report title describing what dev/tooling topics were covered>",
  "summary": "<2-3 sentence executive summary of the key dev/tooling insights>",
  "key_takeaways": [
    "<specific, actionable takeaway 1>",
    "<specific, actionable takeaway 2>",
    "<specific, actionable takeaway 3>"
  ],
  "action_items": [
    "<concrete action item with owner and timeframe>",
    "<concrete action item with owner and timeframe>"
  ],
  "relevance_score": <0.0-1.0 — how relevant is this to the business context above>,
  "business_application": "<1-2 sentences: how specifically does this apply to a 15-dev shop transitioning to AI?>"
}}
"""
)
