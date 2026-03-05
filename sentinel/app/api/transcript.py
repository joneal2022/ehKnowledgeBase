"""Transcript API — direct transcript download as a .txt file."""
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import Response

from app.services.youtube import TranscriptUnavailableError, YouTubeService

router = APIRouter(tags=["transcript"])


@router.post("/transcript/download")
async def download_transcript(url: str = Form(...)) -> Response:
    """Accept a YouTube URL and return a plain-text transcript file download."""
    service = YouTubeService()
    try:
        result = await service.extract(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TranscriptUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    date_str = result.published_at.date().isoformat() if result.published_at else "unknown"
    content = (
        f"Title:  {result.original_title or 'Unknown'}\n"
        f"Author: {result.author or 'Unknown'}\n"
        f"URL:    {url}\n"
        f"Date:   {date_str}\n"
        "\n---\n\n"
        f"{result.transcript}"
    )
    filename = f"transcript_{result.video_id}.txt"
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
