"""LangFuse tracing service — gracefully disabled when keys not set."""
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class TracingService:
    """Wraps LangFuse tracing. All methods are no-ops when not configured."""

    def __init__(self):
        self._client = None
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("LangFuse tracing enabled: %s", settings.LANGFUSE_HOST)
            except Exception as exc:
                logger.warning("LangFuse init failed — tracing disabled: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def start_trace(self, name: str, **metadata: Any):
        """Start a new trace. Returns trace object or None if disabled."""
        if not self._client:
            return None
        try:
            return self._client.trace(name=name, metadata=metadata)
        except Exception as exc:
            logger.warning("LangFuse start_trace failed: %s", exc)
            return None

    def get_trace_id(self, trace) -> str | None:
        """Extract trace ID string from a trace object, or None."""
        if trace is None:
            return None
        try:
            return str(trace.id)
        except Exception:
            return None

    def flush(self) -> None:
        """Flush pending events to LangFuse. Safe to call when disabled."""
        if self._client:
            try:
                self._client.flush()
            except Exception as exc:
                logger.warning("LangFuse flush failed: %s", exc)


_tracing_service: TracingService | None = None


def get_tracing_service() -> TracingService:
    global _tracing_service
    if _tracing_service is None:
        _tracing_service = TracingService()
    return _tracing_service


def reset_tracing_service() -> None:
    """Reset singleton — used in tests."""
    global _tracing_service
    _tracing_service = None
