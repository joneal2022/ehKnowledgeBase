"""Executive summary + title generation prompt — cloud model, single call."""

PROMPT_TEMPLATE = """You are analyzing a video that was part of a Skool community live event.
The original title is generic and unhelpful: "{original_title}"

Based on all the insights extracted below, perform two tasks:

TASK 1 - EXECUTIVE SUMMARY:
Create a concise executive summary with:
- TL;DR (3 sentences max)
- Don't Miss (the single most important insight from the entire video)
- Domain breakdown (which domains were covered and what stood out per domain)

TASK 2 - GENERATE TITLE:
Create a descriptive, specific title (max 80 characters) that captures the
main topics covered. Make it informative enough that someone scanning a list
would know exactly what value this video provides.

Bad titles: "Live Recording Jan 15", "Weekly Update", "Community Call"
Good titles: "RAG Architecture Deep-Dive + AI Consulting Pricing Strategies"

{few_shot_examples}

DOMAIN REPORTS:
{domain_reports_text}

Respond with ONLY a JSON object:
{{
  "title": "<generated title, max 80 chars>",
  "tldr": "<3 sentences max executive summary>",
  "dont_miss": "<single most important insight from the entire video>",
  "domain_breakdown": {{
    "dev_tooling": "<1 sentence summary or null if not covered>",
    "ai_solutions": "<1 sentence summary or null if not covered>",
    "business_dev": "<1 sentence summary or null if not covered>"
  }}
}}
"""
