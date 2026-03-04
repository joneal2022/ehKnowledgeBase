"""Sources API — JSON endpoints for source ingestion and listing."""
import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.job import ProcessingJob
from app.models.source import ProcessingStatus, Source, SourceType
from app.schemas.source import SourceResponse, YouTubeSubmitRequest
from app.templates_env import templates
from app.workers.tasks import run_pipeline

router = APIRouter(tags=["sources"])


@router.post("/sources/youtube", response_model=SourceResponse, status_code=202)
async def submit_youtube_url(
    body: YouTubeSubmitRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SourceResponse:
    """Accept a YouTube URL, create a pending Source + ProcessingJob, enqueue pipeline.

    Returns 202 Accepted — processing happens asynchronously via Celery.
    Sets HX-Trigger: refreshSources so the HTMX source list refreshes automatically.
    """
    source = Source(
        source_type=SourceType.youtube,
        url=body.url,
        processing_status=ProcessingStatus.pending,
    )
    session.add(source)
    await session.flush()  # populate source.id without full commit

    job = ProcessingJob(source_id=source.id, status="queued")
    session.add(job)
    await session.commit()
    await session.refresh(source)

    # Enqueue the Celery pipeline task
    task_result = run_pipeline.delay(str(source.id))
    job.celery_task_id = task_result.id
    await session.commit()

    # Tell HTMX to refresh the source list
    response.headers["HX-Trigger"] = "refreshSources"

    return SourceResponse.model_validate(source)


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[SourceResponse]:
    """Return all sources, newest first."""
    result = await session.execute(
        select(Source).order_by(Source.created_at.desc())
    )
    sources = result.scalars().all()
    return [SourceResponse.model_validate(s) for s in sources]


@router.post("/sources/{source_id}/reprocess", response_model=SourceResponse, status_code=202)
async def reprocess_source(
    source_id: uuid.UUID,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SourceResponse:
    """Re-enqueue the pipeline for a failed or completed source."""
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Source not found")

    source.processing_status = ProcessingStatus.pending
    job = ProcessingJob(source_id=source.id, status="queued")
    session.add(job)
    await session.commit()

    task_result = run_pipeline.delay(str(source.id))
    job.celery_task_id = task_result.id
    await session.commit()

    response.headers["HX-Trigger"] = "refreshSources"
    return SourceResponse.model_validate(source)


@router.get("/sources/{source_id}/title-display", response_class=HTMLResponse)
async def title_display(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Return the inline title display fragment (used by Cancel button)."""
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        return HTMLResponse("<span>Not found</span>", status_code=404)
    return templates.TemplateResponse(
        "components/inline_title_display.html",
        {"request": {}, "source": source},
    )


@router.get("/sources/{source_id}/title-edit", response_class=HTMLResponse)
async def title_edit(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Return the inline title edit form (triggered by double-click)."""
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        return HTMLResponse("<span>Not found</span>", status_code=404)
    return templates.TemplateResponse(
        "components/inline_title_edit.html",
        {"request": {}, "source": source},
    )
