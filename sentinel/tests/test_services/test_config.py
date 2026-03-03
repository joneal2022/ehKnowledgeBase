"""Unit tests for app/config.py — Task 1 (Infrastructure).

These tests require NO Docker or running services.
They verify that task → model routing is correct and env var overrides work.
"""
import os

import pytest

from app.config import Settings


def make_settings(**overrides) -> Settings:
    """Create a Settings instance with custom env vars."""
    env = {
        "OLLAMA_LOCAL_URL": "http://localhost:11434",
        "OLLAMA_CLOUD_URL": "https://api.ollama.com",
        "OLLAMA_CLOUD_API_KEY": "test-key",
        "OLLAMA_MODEL_PREPROCESS": "qwen2.5:7b",
        "OLLAMA_MODEL_CLASSIFY": "qwen2.5:7b",
        "OLLAMA_MODEL_EMBED": "nomic-embed-text",
        "OLLAMA_MODEL_SEGMENT": "deepseek-v3",
        "OLLAMA_MODEL_REPORT": "deepseek-v3",
        "OLLAMA_MODEL_SYNTHESIZE": "deepseek-v3",
        "OLLAMA_MODEL_TITLE": "deepseek-v3",
        "OLLAMA_MODEL_EDUCATE": "deepseek-v3",
        "OLLAMA_MODEL_CHAT": "qwen2.5:14b",
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel_test",
        "DATABASE_URL_SYNC": "postgresql://postgres:postgres@localhost:5432/sentinel_test",
        "REDIS_URL": "redis://localhost:6379/1",
        **overrides,
    }
    # Temporarily patch os.environ for the duration of Settings init
    original = {k: os.environ.get(k) for k in env}
    try:
        os.environ.update(env)
        return Settings()
    finally:
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestGetModelForTask:
    def test_preprocess_returns_local_model(self):
        s = make_settings(OLLAMA_MODEL_PREPROCESS="qwen2.5:7b")
        assert s.get_model_for_task("preprocess") == "qwen2.5:7b"

    def test_classify_returns_local_model(self):
        s = make_settings(OLLAMA_MODEL_CLASSIFY="qwen2.5:7b")
        assert s.get_model_for_task("classify") == "qwen2.5:7b"

    def test_embed_returns_embed_model(self):
        s = make_settings(OLLAMA_MODEL_EMBED="nomic-embed-text")
        assert s.get_model_for_task("embed") == "nomic-embed-text"

    def test_segment_returns_cloud_model(self):
        s = make_settings(OLLAMA_MODEL_SEGMENT="deepseek-v3")
        assert s.get_model_for_task("segment") == "deepseek-v3"

    def test_report_returns_cloud_model(self):
        s = make_settings(OLLAMA_MODEL_REPORT="deepseek-v3")
        assert s.get_model_for_task("report") == "deepseek-v3"

    def test_synthesize_returns_cloud_model(self):
        s = make_settings(OLLAMA_MODEL_SYNTHESIZE="deepseek-v3")
        assert s.get_model_for_task("synthesize") == "deepseek-v3"

    def test_chat_returns_chat_model(self):
        s = make_settings(OLLAMA_MODEL_CHAT="qwen2.5:14b")
        assert s.get_model_for_task("chat") == "qwen2.5:14b"

    def test_unknown_task_returns_report_fallback(self):
        s = make_settings(OLLAMA_MODEL_REPORT="deepseek-v3")
        result = s.get_model_for_task("totally_unknown_task")
        assert result == "deepseek-v3"

    def test_classify_escalation_uses_cloud_model(self):
        """classify_escalation must route to cloud, not local."""
        s = make_settings(OLLAMA_MODEL_SEGMENT="deepseek-v3", OLLAMA_MODEL_CLASSIFY="qwen2.5:7b")
        escalation_model = s.get_model_for_task("classify_escalation")
        local_model = s.get_model_for_task("classify")
        # escalation must use a different (cloud) model
        assert escalation_model != local_model


class TestSettingsEnvOverride:
    def test_custom_local_url(self):
        s = make_settings(OLLAMA_LOCAL_URL="http://custom-host:11434")
        assert s.OLLAMA_LOCAL_URL == "http://custom-host:11434"

    def test_custom_embed_model(self):
        """Confirm embed model can be overridden — never hardcoded."""
        s = make_settings(OLLAMA_MODEL_EMBED="custom-embed-model")
        assert s.OLLAMA_MODEL_EMBED == "custom-embed-model"
        assert s.get_model_for_task("embed") == "custom-embed-model"

    def test_embed_model_is_not_hardcoded(self):
        """The embed model must come from env, not be hardcoded as 'nomic-embed-text'."""
        s = make_settings(OLLAMA_MODEL_EMBED="my-custom-embedder")
        assert s.get_model_for_task("embed") == "my-custom-embedder"
