"""Integration test fixtures — require Docker (PostgreSQL + pgvector, Redis)."""
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

SENTINEL_DIR = Path(__file__).parents[2]  # sentinel/
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel_test"


@pytest.fixture(scope="session")
def apply_migrations():
    """Wipe and re-apply the full migration to sentinel_test."""
    subprocess.run(
        ["uv", "run", "alembic", "downgrade", "base"],
        cwd=SENTINEL_DIR, check=False, capture_output=True,
    )
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=SENTINEL_DIR, check=True,
    )
    yield


@pytest_asyncio.fixture
async def db_session(apply_migrations):
    """Async session that rolls back after each test — no persistent side effects."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
