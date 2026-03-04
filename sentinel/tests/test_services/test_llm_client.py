"""Unit tests for LLMClient and parse_llm_json — Task 4."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_client import (
    InferenceTarget,
    LLMClient,
    TASK_ROUTING,
    parse_llm_json,
)


# ── parse_llm_json ─────────────────────────────────────────────────────────────

class TestParseLlmJson:
    def test_parses_plain_json(self):
        result = parse_llm_json('{"domain": "ai_solutions", "confidence": 0.9}')
        assert result == {"domain": "ai_solutions", "confidence": 0.9}

    def test_strips_json_code_fence(self):
        text = '```json\n{"domain": "dev_tooling", "confidence": 0.85}\n```'
        result = parse_llm_json(text)
        assert result["domain"] == "dev_tooling"

    def test_strips_plain_code_fence(self):
        text = '```\n{"domain": "business_dev"}\n```'
        result = parse_llm_json(text)
        assert result["domain"] == "business_dev"

    def test_strips_fence_with_surrounding_text(self):
        """Ollama sometimes adds prose before the JSON block."""
        text = 'Here is the classification:\n```json\n{"domain": "ai_solutions"}\n```'
        result = parse_llm_json(text)
        assert result["domain"] == "ai_solutions"

    def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_llm_json("this is not json at all")

    def test_empty_fence_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_llm_json("```json\n\n```")

    def test_json_with_whitespace_padding(self):
        result = parse_llm_json('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}

    def test_realistic_classify_response(self):
        text = '{"domain": "ai_solutions", "confidence": 0.87, "reasoning": "Discusses RAG architecture"}'
        result = parse_llm_json(text)
        assert result["domain"] == "ai_solutions"
        assert result["confidence"] == 0.87
        assert "reasoning" in result

    def test_realistic_fenced_classify_response(self):
        """Mirrors actual Ollama output with markdown fence wrapping."""
        text = (
            "```json\n"
            '{"domain": "business_dev", "confidence": 0.72, '
            '"reasoning": "Discusses client acquisition strategy"}\n'
            "```"
        )
        result = parse_llm_json(text)
        assert result["domain"] == "business_dev"
        assert result["confidence"] == 0.72


# ── task routing ───────────────────────────────────────────────────────────────

class TestTaskRouting:
    def test_classify_routes_local(self):
        assert TASK_ROUTING["classify"] == InferenceTarget.LOCAL

    def test_preprocess_routes_local(self):
        assert TASK_ROUTING["preprocess"] == InferenceTarget.LOCAL

    def test_embed_routes_local(self):
        assert TASK_ROUTING["embed"] == InferenceTarget.LOCAL

    def test_classify_escalation_routes_cloud(self):
        assert TASK_ROUTING["classify_escalation"] == InferenceTarget.CLOUD

    def test_segment_routes_cloud(self):
        assert TASK_ROUTING["segment"] == InferenceTarget.CLOUD

    def test_report_routes_cloud(self):
        assert TASK_ROUTING["report"] == InferenceTarget.CLOUD

    def test_synthesize_routes_cloud(self):
        assert TASK_ROUTING["synthesize"] == InferenceTarget.CLOUD


# ── LLMClient.complete ─────────────────────────────────────────────────────────

class TestLLMClientComplete:
    @pytest.fixture
    def client(self):
        return LLMClient()

    def _make_mock_response(self, content: str) -> MagicMock:
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {"response": content}
        return mock

    async def test_classify_calls_local_endpoint(self, client):
        mock_resp = self._make_mock_response('{"domain": "ai_solutions", "confidence": 0.9}')
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.complete("classify", "Classify this section.")

        call_url = mock_post.call_args[0][0]
        assert "api/generate" in call_url
        # Local URL should not contain cloud domain
        assert "ollama.com" not in call_url

    async def test_report_calls_cloud_endpoint(self, client):
        mock_resp = self._make_mock_response('{"title": "AI Report"}')
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.complete("report", "Generate a report.")

        call_url = mock_post.call_args[0][0]
        # Cloud endpoint
        assert "api/generate" in call_url
        call_kwargs = mock_post.call_args[1]
        # Cloud call should include auth header
        assert "Authorization" in call_kwargs.get("headers", {})

    async def test_complete_returns_response_text(self, client):
        expected = '{"domain": "dev_tooling", "confidence": 0.95, "reasoning": "About Claude Code"}'
        mock_resp = self._make_mock_response(expected)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.complete("classify", "Some prompt")
        assert result == expected

    async def test_model_name_comes_from_config_not_hardcoded(self, client):
        """TC-1: model name must come from settings.get_model_for_task(), never hardcoded."""
        mock_resp = self._make_mock_response("{}")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await client.complete("classify", "prompt")

        payload = mock_post.call_args[1]["json"]
        # The model in the payload must match what config returns for "classify"
        from app.config import settings
        assert payload["model"] == settings.get_model_for_task("classify")

    async def test_unknown_task_defaults_to_cloud(self, client):
        mock_resp = self._make_mock_response("{}")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await client.complete("unknown_task", "prompt")

        call_kwargs = mock_post.call_args[1]
        assert "Authorization" in call_kwargs.get("headers", {})
