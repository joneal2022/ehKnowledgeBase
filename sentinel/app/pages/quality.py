"""Quality dashboard page — GET /quality."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.feedback import Feedback
from app.models.prompt_version import PromptVersion
from app.models.source import Source
from app.templates_env import templates

router = APIRouter(tags=["pages"])


@router.get("/quality")
async def quality_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    sources_result = await session.execute(
        select(Source).order_by(Source.created_at.desc())
    )
    sources = sources_result.scalars().all()

    feedback_result = await session.execute(
        select(Feedback).order_by(Feedback.created_at.desc()).limit(100)
    )
    feedback_items = feedback_result.scalars().all()

    pv_result = await session.execute(
        select(PromptVersion)
        .where(PromptVersion.is_active.is_(True))
        .order_by(PromptVersion.activated_at.desc())
    )
    prompt_versions = pv_result.scalars().all()

    # Aggregate stats in Python (avoids complex SQL for MVP)
    status_counts = {}
    for s in sources:
        key = s.processing_status.value
        status_counts[key] = status_counts.get(key, 0) + 1

    thumbs_up = sum(
        1
        for f in feedback_items
        if f.target_type.value == "classification" and f.rating == 1
    )
    thumbs_down = sum(
        1
        for f in feedback_items
        if f.target_type.value == "classification" and f.rating == 0
    )

    report_ratings = [
        f.rating
        for f in feedback_items
        if f.target_type.value == "report" and f.rating is not None
    ]
    avg_report_rating = (
        round(sum(report_ratings) / len(report_ratings), 1) if report_ratings else None
    )

    return templates.TemplateResponse(
        request,
        "pages/quality.html",
        {
            "total_sources": len(sources),
            "status_counts": status_counts,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "avg_report_rating": avg_report_rating,
            "report_rating_count": len(report_ratings),
            "prompt_versions": prompt_versions,
        },
    )
