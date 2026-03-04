"""Extract node — pulls YouTube transcript and updates Source record in DB."""
from langchain_core.runnables import RunnableConfig
from sqlalchemy import select

from app.models.source import ProcessingStatus, Source
from app.pipeline.state import PipelineState
from app.services.youtube import TranscriptUnavailableError, YouTubeService


async def extract_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Fetch YouTube transcript + metadata; update Source record to processing.

    Returns state updates:
      transcript, original_title, author, errors
    """
    cfg = config.get("configurable", {})
    session = cfg["session"]
    youtube_svc: YouTubeService = cfg.get("youtube_service") or YouTubeService()

    # Mark source as processing
    result = await session.execute(
        select(Source).where(Source.id == state["source_id"])
    )
    source = result.scalar_one()
    source.processing_status = ProcessingStatus.processing
    await session.flush()

    try:
        yt_result = await youtube_svc.extract(state["url"])
    except TranscriptUnavailableError as exc:
        return {
            "transcript": "",
            "original_title": None,
            "author": None,
            "errors": [f"extract: transcript unavailable — {exc}"],
        }
    except Exception as exc:
        return {
            "transcript": "",
            "original_title": None,
            "author": None,
            "errors": [f"extract: unexpected error — {exc}"],
        }

    # Persist transcript + metadata back to the Source record
    source.raw_content = yt_result.transcript
    source.original_title = yt_result.original_title
    source.author = yt_result.author
    if yt_result.published_at:
        source.published_at = yt_result.published_at
    await session.flush()

    return {
        "transcript": yt_result.transcript,
        "original_title": yt_result.original_title,
        "author": yt_result.author,
        "errors": [],
    }
