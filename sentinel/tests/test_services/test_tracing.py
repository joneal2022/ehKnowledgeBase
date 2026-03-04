"""Unit tests for TracingService — Task 19."""
from unittest.mock import MagicMock, patch

import pytest

from app.services.tracing import TracingService, reset_tracing_service


class TestTracingServiceDisabled:
    """TracingService is disabled when LANGFUSE keys are not set."""

    def _make_service(self, public_key="", secret_key=""):
        with patch("app.services.tracing.settings") as mock_settings:
            mock_settings.LANGFUSE_PUBLIC_KEY = public_key
            mock_settings.LANGFUSE_SECRET_KEY = secret_key
            mock_settings.LANGFUSE_HOST = "http://localhost:3000"
            return TracingService()

    def test_enabled_is_false_when_keys_empty(self):
        svc = self._make_service(public_key="", secret_key="")
        assert svc.enabled is False

    def test_start_trace_returns_none_when_disabled(self):
        svc = self._make_service()
        result = svc.start_trace("run_pipeline", source_id="abc")
        assert result is None

    def test_get_trace_id_returns_none_for_none_trace(self):
        svc = self._make_service()
        assert svc.get_trace_id(None) is None

    def test_flush_does_not_raise_when_disabled(self):
        svc = self._make_service()
        svc.flush()  # should not raise


class TestTracingServiceEnabled:
    """TracingService initializes LangFuse when keys are present."""

    def _make_service_with_mock_langfuse(self):
        mock_langfuse_class = MagicMock()
        mock_client = MagicMock()
        mock_langfuse_class.return_value = mock_client

        with patch("app.services.tracing.settings") as mock_settings:
            mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
            mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
            mock_settings.LANGFUSE_HOST = "http://localhost:3000"
            with patch.dict("sys.modules", {"langfuse": MagicMock(Langfuse=mock_langfuse_class)}):
                svc = TracingService()
                svc._client = mock_client  # inject mock after init
        return svc, mock_client

    def test_get_trace_id_returns_string_from_trace(self):
        svc = TracingService.__new__(TracingService)
        svc._client = MagicMock()

        mock_trace = MagicMock()
        mock_trace.id = "trace-abc-123"
        result = svc.get_trace_id(mock_trace)

        assert result == "trace-abc-123"

    def test_start_trace_returns_none_when_client_raises(self):
        svc = TracingService.__new__(TracingService)
        mock_client = MagicMock()
        mock_client.trace.side_effect = RuntimeError("Connection failed")
        svc._client = mock_client

        result = svc.start_trace("run_pipeline")
        assert result is None

    def test_flush_calls_client_flush(self):
        svc = TracingService.__new__(TracingService)
        mock_client = MagicMock()
        svc._client = mock_client

        svc.flush()
        mock_client.flush.assert_called_once()

    def test_flush_does_not_raise_when_client_flush_fails(self):
        svc = TracingService.__new__(TracingService)
        mock_client = MagicMock()
        mock_client.flush.side_effect = RuntimeError("Flush failed")
        svc._client = mock_client

        svc.flush()  # should not raise


class TestTracingServiceInitFailure:
    """When LangFuse raises on init, service is gracefully disabled."""

    def test_enabled_false_when_langfuse_init_raises(self):
        mock_langfuse_module = MagicMock()
        mock_langfuse_module.Langfuse.side_effect = RuntimeError("Cannot connect")

        with patch("app.services.tracing.settings") as mock_settings:
            mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
            mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
            mock_settings.LANGFUSE_HOST = "http://localhost:3000"
            with patch.dict("sys.modules", {"langfuse": mock_langfuse_module}):
                svc = TracingService()

        assert svc.enabled is False
