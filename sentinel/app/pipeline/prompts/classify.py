"""Domain classification prompt — local 7B."""

PROMPT_TEMPLATE = """Classify the following transcript section into exactly one domain:

DOMAINS:
- dev_tooling: Development process, tools, frameworks, coding practices, IDE tips, deployment, testing
- ai_solutions: AI implementation, architecture, solutions design, RAG, agents, LLMs, ML pipelines
- business_dev: Business growth, sales, marketing, ROI, pricing, client acquisition, case studies
- not_relevant: Off-topic, personal anecdotes, housekeeping, Q&A logistics

BOUNDARY RULES:
- "Pricing AI solutions" → business_dev (about business strategy)
- "Technical architecture of a RAG system" → ai_solutions (about implementation)
- "How to sell RAG to enterprise clients" → business_dev (about selling)
- When in doubt: BUILD something = ai_solutions/dev_tooling, SELL/GROW something = business_dev

{few_shot_examples}

Section to classify:
{section_content}

Respond with ONLY a JSON object:
{{"domain": "<domain>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}}
"""
