"""Domain filter view — GET /domain/{domain}."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.section import ContentSection, DomainEnum
from app.models.source import Source
from app.templates_env import templates

router = APIRouter(tags=["pages"])

_DOMAIN_LABELS = {
    "dev_tooling": "Dev Tooling",
    "ai_solutions": "AI Solutions",
    "business_dev": "Business Dev",
}


@router.get("/domain/{domain}")
async def domain_view(
    domain: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    if domain not in _DOMAIN_LABELS:
        raise HTTPException(status_code=404, detail="Unknown domain")

    domain_enum = DomainEnum(domain)

    result = await session.execute(
        select(Source)
        .where(
            exists(
                select(ContentSection.source_id).where(
                    ContentSection.source_id == Source.id,
                    ContentSection.domain == domain_enum,
                )
            )
        )
        .order_by(Source.created_at.desc())
    )
    sources = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "pages/domain_view.html",
        {
            "domain": domain,
            "domain_label": _DOMAIN_LABELS[domain],
            "sources": sources,
        },
    )
