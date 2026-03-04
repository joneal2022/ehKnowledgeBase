"""AI Solutions & Implementation report prompt — cloud model."""

BUSINESS_CONTEXT = """
You are generating insights for the owner of a custom software development company
based in Louisiana with clients in Dallas and Houston. The company has 15 developers
(mostly in India) and is transitioning to also offer AI solutions alongside traditional
custom software. The owner needs actionable intelligence, not academic summaries.

When analyzing content, always consider:
- How does this apply to a company trying to offer AI solutions to clients?
- What AI architectures or patterns are worth adopting?
- What do clients in the Dallas/Houston market actually want?
- Is this technically feasible for a team transitioning into AI?
"""

PROMPT_TEMPLATE = (
    BUSINESS_CONTEXT
    + """

You are generating an executive report for the AI SOLUTIONS & IMPLEMENTATION domain.
This covers: AI architecture patterns, RAG systems, LLM integration, agent frameworks,
ML pipelines, automation, AI project scoping, and implementation strategies.

{few_shot_examples}

TRANSCRIPT SECTIONS CLASSIFIED AS AI_SOLUTIONS:
{sections_text}

Generate a structured executive report. Respond with ONLY a JSON object:
{{
  "title": "<concise report title describing what AI implementation topics were covered>",
  "summary": "<2-3 sentence executive summary of the key AI solutions insights>",
  "key_takeaways": [
    "<specific, actionable takeaway 1>",
    "<specific, actionable takeaway 2>",
    "<specific, actionable takeaway 3>"
  ],
  "action_items": [
    "<concrete action item with owner and timeframe>",
    "<concrete action item with owner and timeframe>"
  ],
  "relevance_score": <0.0-1.0 — how relevant is this to a company offering AI solutions>,
  "business_application": "<1-2 sentences: what AI solutions could this company offer based on these insights?>"
}}
"""
)
