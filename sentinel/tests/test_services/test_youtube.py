"""Unit tests for YouTubeService — Task 3."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.youtube import YouTubeResult, YouTubeService, TranscriptUnavailableError


@pytest.fixture
def svc():
    return YouTubeService()


# ── video ID parsing ───────────────────────────────────────────────────────────

class TestExtractVideoId:
    def test_standard_watch_url(self, svc):
        assert svc.extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_youtu_be_url(self, svc):
        assert svc.extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self, svc):
        assert svc.extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self, svc):
        assert svc.extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_extra_params(self, svc):
        assert svc.extract_video_id(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&list=PLxxx"
        ) == "dQw4w9WgXcQ"

    def test_invalid_url_raises_value_error(self, svc):
        with pytest.raises(ValueError, match="Cannot parse video ID"):
            svc.extract_video_id("https://vimeo.com/123456")

    def test_non_youtube_domain_raises(self, svc):
        with pytest.raises(ValueError):
            svc.extract_video_id("https://example.com/watch?v=abc")


# ── transcript fetching ────────────────────────────────────────────────────────

class TestFetchTranscript:
    async def test_joins_transcript_entries_with_spaces(self, svc):
        from youtube_transcript_api import FetchedTranscriptSnippet
        snippets = [
            FetchedTranscriptSnippet("Hello world", 0.0, 1.5),
            FetchedTranscriptSnippet("this is a test", 1.5, 2.0),
            FetchedTranscriptSnippet("transcript.", 3.5, 1.0),
        ]
        with patch("app.services.youtube.YouTubeTranscriptApi.fetch", return_value=snippets):
            result = await svc._fetch_transcript("test_id")
        assert result == "Hello world this is a test transcript."

    async def test_transcripts_disabled_raises_transcript_unavailable(self, svc):
        from youtube_transcript_api import TranscriptsDisabled
        with patch(
            "app.services.youtube.YouTubeTranscriptApi.fetch",
            side_effect=TranscriptsDisabled("test_id"),
        ):
            with pytest.raises(TranscriptUnavailableError, match="test_id"):
                await svc._fetch_transcript("test_id")

    async def test_no_transcript_found_raises_transcript_unavailable(self, svc):
        from youtube_transcript_api import NoTranscriptFound
        with patch(
            "app.services.youtube.YouTubeTranscriptApi.fetch",
            side_effect=NoTranscriptFound("test_id", [], {}),
        ):
            with pytest.raises(TranscriptUnavailableError):
                await svc._fetch_transcript("test_id")


# ── metadata fetching ──────────────────────────────────────────────────────────

class TestFetchMetadata:
    async def test_returns_title_and_author_from_oembed(self, svc):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "title": "Skool Week 12 - Monday Stream",
            "author_name": "Ed Honour",
        }
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await svc._fetch_metadata("https://www.youtube.com/watch?v=abc")
        assert result["title"] == "Skool Week 12 - Monday Stream"
        assert result["author_name"] == "Ed Honour"

    async def test_oembed_failure_returns_empty_dict(self, svc):
        with patch("httpx.AsyncClient.get", side_effect=Exception("network error")):
            result = await svc._fetch_metadata("https://www.youtube.com/watch?v=abc")
        assert result == {}


# ── full extract ───────────────────────────────────────────────────────────────

class TestExtract:
    async def test_extract_returns_youtube_result(self, svc):
        from youtube_transcript_api import FetchedTranscriptSnippet
        snippets = [FetchedTranscriptSnippet("LangGraph is great for agents.", 0.0, 3.0)]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "title": "Monday Hangout Jan 15",
            "author_name": "Ed Honour",
        }
        with (
            patch("app.services.youtube.YouTubeTranscriptApi.fetch", return_value=snippets),
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        ):
            result = await svc.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert isinstance(result, YouTubeResult)
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.transcript == "LangGraph is great for agents."
        assert result.author == "Ed Honour"

    async def test_original_title_is_raw_youtube_title_not_generated(self, svc):
        """BR-1 / DR-4: original_title must be the raw YouTube title, unchanged.
        The pipeline generates the real title later — this service must NOT modify it.
        """
        from youtube_transcript_api import FetchedTranscriptSnippet
        raw_title = "Monday Hangout Jan 15"   # generic useless YouTube title
        snippets = [FetchedTranscriptSnippet("Content about AI agents.", 0.0, 2.0)]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"title": raw_title, "author_name": "Ed Honour"}

        with (
            patch("app.services.youtube.YouTubeTranscriptApi.fetch", return_value=snippets),
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        ):
            result = await svc.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.original_title == raw_title
        assert result.original_title != result.transcript  # never derives title from content here

    async def test_extract_metadata_failure_still_returns_result(self, svc):
        """Metadata failure is non-fatal — result returned with None title/author."""
        from youtube_transcript_api import FetchedTranscriptSnippet
        snippets = [FetchedTranscriptSnippet("Some transcript text.", 0.0, 2.0)]
        with (
            patch("app.services.youtube.YouTubeTranscriptApi.fetch", return_value=snippets),
            patch("httpx.AsyncClient.get", side_effect=Exception("oembed down")),
        ):
            result = await svc.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.transcript == "Some transcript text."
        assert result.original_title is None
        assert result.author is None

    async def test_extract_transcript_unavailable_raises(self, svc):
        from youtube_transcript_api import TranscriptsDisabled
        with patch(
            "app.services.youtube.YouTubeTranscriptApi.fetch",
            side_effect=TranscriptsDisabled("dQw4w9WgXcQ"),
        ):
            with pytest.raises(TranscriptUnavailableError):
                await svc.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    async def test_published_at_is_none(self, svc):
        """published_at is always None — requires YouTube Data API which we don't use."""
        from youtube_transcript_api import FetchedTranscriptSnippet
        snippets = [FetchedTranscriptSnippet("Text.", 0.0, 1.0)]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"title": "Test", "author_name": "Test"}
        with (
            patch("app.services.youtube.YouTubeTranscriptApi.fetch", return_value=snippets),
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        ):
            result = await svc.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.published_at is None
