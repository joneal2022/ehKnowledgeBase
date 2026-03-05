"""YouTube transcript extraction service.

Extracts transcripts and basic metadata from YouTube URLs.
Does NOT generate titles — original YouTube titles are stored as-is
in sources.original_title. The pipeline generates the real title later.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    FetchedTranscriptSnippet,
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)


class TranscriptUnavailableError(Exception):
    """Raised when no transcript can be retrieved for a video."""


@dataclass
class YouTubeResult:
    url: str
    video_id: str
    transcript: str                      # full transcript text, space-joined (pipeline uses this)
    snippets: list[FetchedTranscriptSnippet]  # raw snippets with start/duration timestamps
    original_title: str | None           # raw YouTube title — stored as-is, never surfaced to user
    author: str | None
    published_at: datetime | None        # not available without YouTube Data API


class YouTubeService:
    """Extracts YouTube transcripts and metadata without requiring an API key."""

    OEMBED_URL = "https://www.youtube.com/oembed"

    def extract_video_id(self, url: str) -> str:
        """Parse a YouTube video ID from any standard URL format."""
        parsed = urlparse(url.strip())
        host = parsed.hostname or ""

        if host == "youtu.be":
            vid = parsed.path.lstrip("/").split("/")[0]
            if vid:
                return vid

        if host in ("www.youtube.com", "youtube.com"):
            if parsed.path == "/watch":
                ids = parse_qs(parsed.query).get("v", [])
                if ids:
                    return ids[0]
            if "/shorts/" in parsed.path:
                return parsed.path.split("/shorts/")[1].split("/")[0]
            if "/embed/" in parsed.path:
                return parsed.path.split("/embed/")[1].split("/")[0]

        raise ValueError(f"Cannot parse video ID from URL: {url!r}")

    async def _fetch_transcript(self, video_id: str) -> list[FetchedTranscriptSnippet]:
        """Fetch transcript from YouTube (blocking call run in executor)."""
        loop = asyncio.get_event_loop()
        api = YouTubeTranscriptApi()
        try:
            fetched = await loop.run_in_executor(
                None,
                lambda: api.fetch(video_id),
            )
        except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript) as exc:
            raise TranscriptUnavailableError(
                f"No transcript available for video {video_id!r}: {exc}"
            ) from exc
        return list(fetched)

    async def _fetch_metadata(self, url: str) -> dict:
        """Fetch title + author via YouTube's oembed endpoint (no API key needed)."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    self.OEMBED_URL, params={"url": url, "format": "json"}
                )
                resp.raise_for_status()
                return resp.json()
            except Exception:
                return {}

    async def extract(self, url: str) -> YouTubeResult:
        """Extract transcript and metadata for a YouTube URL.

        Raises:
            ValueError: if the URL is not a recognisable YouTube URL.
            TranscriptUnavailableError: if the video has no accessible transcript.
        """
        video_id = self.extract_video_id(url)
        snippets, metadata = await asyncio.gather(
            self._fetch_transcript(video_id),
            self._fetch_metadata(url),
        )
        return YouTubeResult(
            url=url,
            video_id=video_id,
            transcript=" ".join(s.text for s in snippets),
            snippets=snippets,
            original_title=metadata.get("title"),   # raw YouTube title — NOT the generated one
            author=metadata.get("author_name"),
            published_at=None,                       # requires YouTube Data API — out of scope
        )
