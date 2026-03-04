"""Celery worker tasks — background pipeline execution."""
import asyncio

from celery import Celery

from app.config import settings

celery_app = Celery(
    "sentinel",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.task_serializer = "json"


@celery_app.task(name="run_pipeline", bind=True)
def run_pipeline(self, source_id: str) -> dict:
    """Celery task: run the full LangGraph pipeline for a source."""
    return asyncio.run(_run_async(self.request.id, source_id))


async def _run_async(celery_task_id: str, source_id: str) -> dict:
    """Async implementation of the pipeline run."""
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.source import Source
    from app.pipeline.graph import get_compiled_graph
    from app.services.llm_client import LLMClient
    from app.services.youtube import YouTubeService

    graph = get_compiled_graph()
    llm_client = LLMClient()
    youtube_svc = YouTubeService()

    async with async_session_factory() as session:
        result = await session.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one()

        initial_state = {
            "source_id": source_id,
            "url": source.url,
            "transcript": "",
            "original_title": None,
            "author": None,
            "preprocessed_transcript": "",
            "sections": [],
            "classified_sections": [],
            "reports": {},
            "synthesis": {},
            "errors": [],
            "prompt_versions": {},
        }
        config = {
            "configurable": {
                "session": session,
                "llm_client": llm_client,
                "youtube_service": youtube_svc,
            }
        }

        final_state = await graph.ainvoke(initial_state, config=config)
        await session.commit()

        return {"status": "completed", "errors": final_state.get("errors", [])}
