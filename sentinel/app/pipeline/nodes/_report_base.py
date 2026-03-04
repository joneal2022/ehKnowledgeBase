"""Shared report generation logic for domain report nodes."""
from app.config import settings
from app.models.report import Report, ReportType
from app.models.section import DomainEnum
from app.pipeline.prompts.manager import PromptManager
from app.services.llm_client import LLMClient, parse_llm_json


async def generate_domain_report(
    state: dict,
    session,
    llm_client: LLMClient,
    domain: str,
    prompt_name: str,
) -> dict:
    """Generate a report for sections matching domain.

    Returns state update dict: {reports, prompt_versions, errors}
    """
    sections = [
        s for s in state.get("classified_sections", [])
        if s.get("domain") == domain
    ]
    if not sections:
        return {"reports": {}, "prompt_versions": {}, "errors": []}

    prompt_manager = PromptManager(session)
    prompt_template = await prompt_manager.get_active_prompt(prompt_name)
    version_hash = await prompt_manager.get_prompt_version_hash(prompt_name)

    sections_text = "\n\n".join(s.get("content", "") for s in sections)
    prompt = prompt_template.format(sections_text=sections_text, few_shot_examples="")

    try:
        raw = await llm_client.complete("report", prompt)
        parsed = parse_llm_json(raw)
    except Exception as exc:
        return {
            "reports": {},
            "prompt_versions": {f"report_{domain}": version_hash},
            "errors": [f"report_{domain}: failed to generate report — {exc}"],
        }

    model_used = settings.get_model_for_task("report")

    report_row = Report(
        source_id=state["source_id"],
        report_type=ReportType.domain_specific,
        domain=DomainEnum(domain),
        title=parsed.get("title"),
        content=parsed.get("summary"),
        key_takeaways=parsed.get("key_takeaways"),
        action_items=parsed.get("action_items"),
        relevance_score=parsed.get("relevance_score"),
        model_used=model_used,
        prompt_version=version_hash,
    )
    session.add(report_row)

    return {
        "reports": {
            domain: {
                "domain": domain,
                "title": parsed.get("title"),
                "summary": parsed.get("summary"),
                "key_takeaways": parsed.get("key_takeaways"),
                "action_items": parsed.get("action_items"),
                "relevance_score": parsed.get("relevance_score"),
                "model_used": model_used,
                "prompt_version": version_hash,
            }
        },
        "prompt_versions": {f"report_{domain}": version_hash},
        "errors": [],
    }
