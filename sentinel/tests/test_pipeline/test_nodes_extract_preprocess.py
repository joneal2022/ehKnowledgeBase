"""Unit tests for extract_node and preprocess_node — Task 10."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.nodes.extract import extract_node
from app.pipeline.nodes.preprocess import preprocess_node
from app.pipeline.state import PipelineState
from app.models.source import ProcessingStatus
from app.services.youtube import TranscriptUnavailableError, YouTubeResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def _base_state(**kwargs) -> PipelineState:
    defaults = {
        "source_id": str(uuid.uuid4()),
        "url": "https://www.youtube.com/watch?v=test123",
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
    defaults.update(kwargs)
    return defaults  # type: ignore


def _make_config(session=None, youtube_svc=None, llm_client=None):
    return {
        "configurable": {
            "session": session or AsyncMock(),
            "youtube_service": youtube_svc,
            "llm_client": llm_client,
        }
    }


def _make_yt_result(transcript="hello world", original_title="Live Jan 1", author="Channel"):
    return YouTubeResult(
        url="https://www.youtube.com/watch?v=test123",
        video_id="test123",
        transcript=transcript,
        original_title=original_title,
        author=author,
        published_at=None,
    )


def _make_session_with_source():
    """Build a mock session that returns a mock Source on execute()."""
    source = MagicMock()
    source.processing_status = ProcessingStatus.pending
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = source
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return session, source


# ── extract_node ───────────────────────────────────────────────────────────────

class TestExtractNode:
    @pytest.mark.asyncio
    async def test_returns_transcript_from_youtube_service(self):
        session, source = _make_session_with_source()
        yt_svc = AsyncMock()
        yt_svc.extract = AsyncMock(return_value=_make_yt_result(transcript="the transcript"))

        result = await extract_node(
            _base_state(),
            _make_config(session=session, youtube_svc=yt_svc),
        )

        assert result["transcript"] == "the transcript"

    @pytest.mark.asyncio
    async def test_returns_original_title_from_youtube(self):
        session, source = _make_session_with_source()
        yt_svc = AsyncMock()
        yt_svc.extract = AsyncMock(return_value=_make_yt_result(original_title="Live Recording Jan 1"))

        result = await extract_node(
            _base_state(),
            _make_config(session=session, youtube_svc=yt_svc),
        )

        assert result["original_title"] == "Live Recording Jan 1"

    @pytest.mark.asyncio
    async def test_marks_source_as_processing(self):
        session, source = _make_session_with_source()
        yt_svc = AsyncMock()
        yt_svc.extract = AsyncMock(return_value=_make_yt_result())

        await extract_node(_base_state(), _make_config(session=session, youtube_svc=yt_svc))

        assert source.processing_status == ProcessingStatus.processing

    @pytest.mark.asyncio
    async def test_persists_transcript_to_source_record(self):
        session, source = _make_session_with_source()
        yt_svc = AsyncMock()
        yt_svc.extract = AsyncMock(return_value=_make_yt_result(transcript="stored transcript"))

        await extract_node(_base_state(), _make_config(session=session, youtube_svc=yt_svc))

        assert source.raw_content == "stored transcript"

    @pytest.mark.asyncio
    async def test_flushes_session_after_update(self):
        session, source = _make_session_with_source()
        yt_svc = AsyncMock()
        yt_svc.extract = AsyncMock(return_value=_make_yt_result())

        await extract_node(_base_state(), _make_config(session=session, youtube_svc=yt_svc))

        session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_transcript_unavailable_returns_error_not_raise(self):
        session, source = _make_session_with_source()
        yt_svc = AsyncMock()
        yt_svc.extract = AsyncMock(side_effect=TranscriptUnavailableError("no captions"))

        result = await extract_node(_base_state(), _make_config(session=session, youtube_svc=yt_svc))

        assert result["transcript"] == ""
        assert len(result["errors"]) == 1
        assert "extract:" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_error_not_raise(self):
        session, source = _make_session_with_source()
        yt_svc = AsyncMock()
        yt_svc.extract = AsyncMock(side_effect=RuntimeError("network down"))

        result = await extract_node(_base_state(), _make_config(session=session, youtube_svc=yt_svc))

        assert result["transcript"] == ""
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_no_errors_on_success(self):
        session, source = _make_session_with_source()
        yt_svc = AsyncMock()
        yt_svc.extract = AsyncMock(return_value=_make_yt_result())

        result = await extract_node(_base_state(), _make_config(session=session, youtube_svc=yt_svc))

        assert result["errors"] == []


# ── preprocess_node ────────────────────────────────────────────────────────────

class TestPreprocessNode:
    def _make_prompt_manager(self, session):
        mgr = AsyncMock()
        mgr.get_active_prompt = AsyncMock(return_value="Clean this: {transcript}\n{few_shot_examples}")
        mgr.get_prompt_version_hash = AsyncMock(return_value="abc123def456")
        return mgr

    @pytest.mark.asyncio
    async def test_returns_cleaned_transcript(self):
        session = AsyncMock()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="Cleaned up transcript.")

        with patch("app.pipeline.nodes.preprocess.PromptManager") as MockPM:
            MockPM.return_value = self._make_prompt_manager(session)
            result = await preprocess_node(
                _base_state(transcript="raw messy transcript"),
                _make_config(session=session, llm_client=llm),
            )

        assert result["preprocessed_transcript"] == "Cleaned up transcript."

    @pytest.mark.asyncio
    async def test_calls_llm_with_preprocess_task(self):
        session = AsyncMock()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="cleaned")

        with patch("app.pipeline.nodes.preprocess.PromptManager") as MockPM:
            MockPM.return_value = self._make_prompt_manager(session)
            await preprocess_node(
                _base_state(transcript="raw transcript"),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_awaited_once()
        call_args = llm.complete.call_args
        assert call_args[0][0] == "preprocess"

    @pytest.mark.asyncio
    async def test_records_prompt_version_hash(self):
        session = AsyncMock()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="cleaned")

        with patch("app.pipeline.nodes.preprocess.PromptManager") as MockPM:
            MockPM.return_value = self._make_prompt_manager(session)
            result = await preprocess_node(
                _base_state(transcript="raw"),
                _make_config(session=session, llm_client=llm),
            )

        assert result["prompt_versions"]["preprocess"] == "abc123def456"

    @pytest.mark.asyncio
    async def test_empty_transcript_skips_llm(self):
        session = AsyncMock()
        llm = AsyncMock()

        with patch("app.pipeline.nodes.preprocess.PromptManager") as MockPM:
            MockPM.return_value = self._make_prompt_manager(session)
            result = await preprocess_node(
                _base_state(transcript=""),
                _make_config(session=session, llm_client=llm),
            )

        llm.complete.assert_not_awaited()
        assert result["preprocessed_transcript"] == ""

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_raw_transcript(self):
        session = AsyncMock()
        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("ollama down"))

        with patch("app.pipeline.nodes.preprocess.PromptManager") as MockPM:
            MockPM.return_value = self._make_prompt_manager(session)
            result = await preprocess_node(
                _base_state(transcript="the raw transcript"),
                _make_config(session=session, llm_client=llm),
            )

        assert result["preprocessed_transcript"] == "the raw transcript"
        assert len(result["errors"]) == 1
        assert "preprocess:" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_no_errors_on_success(self):
        session = AsyncMock()
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="cleaned transcript")

        with patch("app.pipeline.nodes.preprocess.PromptManager") as MockPM:
            MockPM.return_value = self._make_prompt_manager(session)
            result = await preprocess_node(
                _base_state(transcript="raw"),
                _make_config(session=session, llm_client=llm),
            )

        assert result["errors"] == []
