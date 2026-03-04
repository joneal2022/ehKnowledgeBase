"""Video detail page — GET /videos/{source_id}."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.report import Report, ReportType
from app.models.section import ContentSection, DomainEnum
from app.models.source import Source
from app.templates_env import templates

router = APIRouter(tags=["pages"])

_DOMAIN_TABS = [
    {"key": DomainEnum.dev_tooling, "label": "Dev Tooling"},
    {"key": DomainEnum.ai_solutions, "label": "AI Solutions"},
    {"key": DomainEnum.business_dev, "label": "Business Dev"},
]


@router.get("/videos/{source_id}")
async def video_detail(
    source_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    try:
        sid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    result = await session.execute(select(Source).where(Source.id == sid))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    report_result = await session.execute(
        select(Report).where(Report.source_id == sid).order_by(Report.created_at)
    )
    reports = report_result.scalars().all()

    section_result = await session.execute(
        select(ContentSection)
        .where(ContentSection.source_id == sid)
        .order_by(ContentSection.section_index)
    )
    sections = section_result.scalars().all()

    exec_summary = next(
        (r for r in reports if r.report_type == ReportType.executive_summary), None
    )

    domain_tabs = [
        {
            "key": tab["key"].value,
            "label": tab["label"],
            "report": next(
                (
                    r
                    for r in reports
                    if r.report_type == ReportType.domain_specific
                    and r.domain == tab["key"]
                ),
                None,
            ),
            "sections": [s for s in sections if s.domain == tab["key"]],
        }
        for tab in _DOMAIN_TABS
    ]

    return templates.TemplateResponse(
        request,
        "pages/video_detail.html",
        {
            "source": source,
            "exec_summary": exec_summary,
            "domain_tabs": domain_tabs,
        },
    )
