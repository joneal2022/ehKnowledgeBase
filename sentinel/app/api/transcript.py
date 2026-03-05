"""Transcript API — direct transcript download as a .txt file."""
import re

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import Response

from app.services.youtube import FetchedTranscriptSnippet, TranscriptUnavailableError, YouTubeService

router = APIRouter(tags=["transcript"])


def _ts(seconds: float) -> str:
    """Convert seconds to [M:SS] or [H:MM:SS] timestamp string."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"[{h}:{m:02}:{sec:02}]" if h else f"[{m}:{sec:02}]"


def _format_with_timestamps(snippets: list[FetchedTranscriptSnippet], interval: int = 30) -> str:
    """Group snippets into paragraphs every `interval` seconds, each prefixed with a timestamp."""
    paragraphs = []
    bucket_texts: list[str] = []
    bucket_start = 0.0

    for snippet in snippets:
        if snippet.start >= bucket_start + interval and bucket_texts:
            paragraphs.append(_ts(bucket_start) + " " + " ".join(bucket_texts))
            bucket_texts = []
            bucket_start = (snippet.start // interval) * interval
        bucket_texts.append(snippet.text)

    if bucket_texts:
        paragraphs.append(_ts(bucket_start) + " " + " ".join(bucket_texts))

    return "\n\n".join(paragraphs)


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
        f"{_format_with_timestamps(result.snippets)}"
    )
    if result.original_title:
        slug = re.sub(r"[^\w\s-]", "", result.original_title)
        slug = re.sub(r"[\s]+", "_", slug).strip("_")[:80]
        filename = f"{slug}.txt"
    else:
        filename = f"transcript_{result.video_id}.txt"
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
