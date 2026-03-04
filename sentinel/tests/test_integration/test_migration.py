"""Integration tests for the Alembic migration — Group 1 (Task 1/2)."""
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SENTINEL_DIR = Path(__file__).parents[2]
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel_test"

EXPECTED_TABLES = {
    "sources",
    "content_sections",
    "reports",
    "knowledge_entries",
    "knowledge_chunks",
    "chat_sessions",
    "chat_messages",
    "processing_jobs",
    "feedback",
    "prompt_versions",
    "few_shot_bank",
}


@pytest.mark.integration
def test_single_migration_head():
    """Alembic history must have exactly one head — no diverging branches."""
    result = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        cwd=SENTINEL_DIR, capture_output=True, text=True, check=True,
    )
    heads = [line for line in result.stdout.strip().splitlines() if line.strip()]
    assert len(heads) == 1, f"Expected 1 migration head, got {len(heads)}: {result.stdout}"


@pytest.mark.integration
async def test_all_expected_tables_created(apply_migrations):
    """alembic upgrade head must create all 11 expected tables."""
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = {row[0] for row in result}
    await engine.dispose()

    missing = EXPECTED_TABLES - tables
    assert not missing, f"Tables missing after migration: {missing}"


@pytest.mark.integration
async def test_pgvector_extension_enabled(apply_migrations):
    """pgvector extension must be installed (required for knowledge_chunks.embedding)."""
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        row = result.fetchone()
    await engine.dispose()

    assert row is not None, "pgvector extension not installed — run: CREATE EXTENSION vector"


@pytest.mark.integration
async def test_embedding_column_is_vector_768(apply_migrations):
    """knowledge_chunks.embedding must be declared as vector(768)."""
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT atttypmod
            FROM pg_attribute
            JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
            WHERE pg_class.relname = 'knowledge_chunks'
              AND pg_attribute.attname = 'embedding'
              AND NOT pg_attribute.attisdropped
        """))
        row = result.fetchone()
    await engine.dispose()

    assert row is not None, "embedding column not found on knowledge_chunks"
    # vector(768) stores typmod as 768
    assert row[0] == 768, f"Expected vector(768), got vector({row[0]})"


@pytest.mark.integration
async def test_tsvector_column_exists(apply_migrations):
    """knowledge_chunks.search_text must exist as a tsvector GENERATED column."""
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'knowledge_chunks'
              AND column_name = 'search_text'
        """))
        row = result.fetchone()
    await engine.dispose()

    assert row is not None, "search_text column not found on knowledge_chunks"
    assert row[0] == "tsvector", f"Expected tsvector, got {row[0]}"
