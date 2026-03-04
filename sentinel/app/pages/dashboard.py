"""Dashboard page routes — returns HTML for HTMX pages."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.source import Source
from app.templates_env import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=templates.TemplateResponse.__class__)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Source).order_by(Source.created_at.desc())
    )
    sources = result.scalars().all()
    return templates.TemplateResponse(
        request, "pages/dashboard.html", {"sources": sources}
    )


@router.get("/sources/feed")
async def sources_feed(request: Request, session: AsyncSession = Depends(get_session)):
    """HTMX fragment — returns just the source list HTML.

    The dashboard source list div polls/triggers this endpoint.
    """
    result = await session.execute(
        select(Source).order_by(Source.created_at.desc())
    )
    sources = result.scalars().all()
    return templates.TemplateResponse(
        request, "fragments/source_list.html", {"sources": sources}
    )
