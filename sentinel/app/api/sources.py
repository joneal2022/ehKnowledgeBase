"""Sources API — JSON endpoints for source ingestion and listing."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.job import ProcessingJob
from app.models.source import ProcessingStatus, Source, SourceType
from app.schemas.source import SourceResponse, YouTubeSubmitRequest
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
