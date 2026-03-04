"""Shared pytest fixtures for the Sentinel test suite."""
import os

import pytest

# Force test env vars before any app imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel_test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://postgres:postgres@localhost:5432/sentinel_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("OLLAMA_LOCAL_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_CLOUD_API_KEY", "test-key")


@pytest.fixture(scope="session")
def settings():
    """Return a Settings instance loaded from env."""
    from app.config import Settings
    return Settings()
