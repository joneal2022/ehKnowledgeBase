"""Feedback API — collects ratings, corrections, and title edits."""
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.feedback import Feedback, FeedbackTargetType
from app.models.report import Report
from app.models.section import ContentSection
from app.models.source import Source
from app.schemas.feedback import FeedbackRequest, TitlePatchRequest
from app.services.prompt_evolution import PromptEvolutionService
from app.templates_env import templates

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_class=HTMLResponse)
async def submit_feedback(
    body: FeedbackRequest,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Accept any feedback event; store to DB; trigger Tier 2 evolution if warranted."""
    target_uuid = uuid.UUID(body.target_id)

    fb = Feedback(
        target_type=body.target_type,
        target_id=target_uuid,
        rating=body.rating,
        correction=body.correction,
        notes=body.notes,
    )
    session.add(fb)
    await session.flush()

    evolution = PromptEvolutionService(session)
    correction_applied = False

    # Tier 2 Loop 2A: Classification correction → few-shot accumulation
    if body.target_type == FeedbackTargetType.classification and body.correction:
        correct_domain = body.correction.get("correct_domain")
        if correct_domain:
            result = await session.execute(
                select(ContentSection).where(ContentSection.id == target_uuid)
            )
            section = result.scalar_one_or_none()
            if section:
                original_domain = section.domain.value if section.domain else "not_relevant"
                await evolution.process_classification_correction(
                    section_content=section.content,
                    original_domain=original_domain,
                    correct_domain=correct_domain,
                    feedback_id=fb.id,
                )
                correction_applied = True

    # Loop 2B: Report rating tracking (stored via feedback row — aggregated at query time)
    elif body.target_type == FeedbackTargetType.report and body.rating is not None:
        await evolution.process_report_rating(
            report_id=target_uuid,
            rating=body.rating,
            feedback_id=fb.id,
        )

    await session.commit()

    return templates.TemplateResponse(
        "fragments/feedback_confirmed.html",
        {
            "request": {},
            "target_type": body.target_type,
            "target_id": body.target_id,
            "correction_applied": correction_applied,
        },
    )


@router.patch("/sources/{source_id}/title", response_class=HTMLResponse)
async def patch_title(
    source_id: uuid.UUID,
    body: TitlePatchRequest,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Inline title edit — updates Source.title and stores Loop 2D feedback."""
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        return HTMLResponse("<span class='text-red-500'>Source not found</span>", status_code=404)

    old_title = source.title or ""
    source.title = body.title.strip()

    fb = Feedback(
        target_type=FeedbackTargetType.title,
        target_id=source_id,
        rating=None,
        correction={"old_title": old_title, "new_title": body.title.strip()},
    )
    session.add(fb)
    await session.flush()

    evolution = PromptEvolutionService(session)
    await evolution.process_title_correction(
        old_title=old_title,
        new_title=body.title.strip(),
        feedback_id=fb.id,
    )

    await session.commit()

    return templates.TemplateResponse(
        "components/inline_title_display.html",
        {"request": {}, "source": source},
    )
