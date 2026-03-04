"""Integration tests for DB models — Group 1 (Task 2).

Covers: CRUD, CASCADE deletes, vector(768) insert + dimension check,
tsvector GENERATED column auto-population and keyword search.
"""
import pytest
from sqlalchemy import select, text

from app.models.chat import ChatMessage, ChatSession
from app.models.job import ProcessingJob
from app.models.knowledge import DomainEnum, KnowledgeChunk, KnowledgeEntry
from app.models.report import Report, ReportType
from app.models.section import ContentSection
from app.models.source import ProcessingStatus, Source, SourceType


# ── helpers ────────────────────────────────────────────────────────────────────

def make_source(**kwargs) -> Source:
    defaults = dict(source_type=SourceType.youtube, url="https://youtube.com/watch?v=test")
    return Source(**{**defaults, **kwargs})


# ── CRUD ───────────────────────────────────────────────────────────────────────

@pytest.mark.integration
async def test_source_crud(db_session):
    """Source can be created and read back from the real DB."""
    source = make_source(
        title="AI Agent Frameworks Compared",
        original_title="Skool Week 12 - Monday Stream",
        raw_content="Long transcript about LangGraph and CrewAI...",
    )
    db_session.add(source)
    await db_session.flush()

    result = await db_session.execute(select(Source).where(Source.id == source.id))
    fetched = result.scalar_one()

    assert fetched.source_type == SourceType.youtube
    assert fetched.title == "AI Agent Frameworks Compared"
    assert fetched.original_title == "Skool Week 12 - Monday Stream"
    assert fetched.processing_status == ProcessingStatus.pending


@pytest.mark.integration
async def test_source_title_and_original_title_are_independent_columns(db_session):
    """DR-4 / BR-1: title (generated) and original_title (YouTube raw) are separate DB columns."""
    source = make_source(
        title="Five DevOps Tools That Changed Our Workflow",
        original_title="Monday Hangout - random title",
    )
    db_session.add(source)
    await db_session.flush()

    result = await db_session.execute(select(Source).where(Source.id == source.id))
    fetched = result.scalar_one()

    assert fetched.title != fetched.original_title
    assert fetched.title == "Five DevOps Tools That Changed Our Workflow"
    assert fetched.original_title == "Monday Hangout - random title"


# ── CASCADE deletes ────────────────────────────────────────────────────────────

@pytest.mark.integration
async def test_delete_source_cascades_to_content_sections(db_session):
    """CASCADE: deleting a Source deletes all its ContentSections."""
    source = make_source()
    db_session.add(source)
    await db_session.flush()

    section = ContentSection(
        source_id=source.id,
        section_index=0,
        content="LangGraph enables stateful multi-agent workflows.",
    )
    db_session.add(section)
    await db_session.flush()
    section_id = section.id

    await db_session.delete(source)
    await db_session.flush()

    result = await db_session.execute(
        select(ContentSection).where(ContentSection.id == section_id)
    )
    assert result.scalar_one_or_none() is None, "ContentSection must be CASCADE deleted with Source"


@pytest.mark.integration
async def test_delete_source_cascades_to_reports(db_session):
    """CASCADE: deleting a Source deletes all its Reports."""
    source = make_source()
    db_session.add(source)
    await db_session.flush()

    report = Report(
        source_id=source.id,
        report_type=ReportType.domain_specific,
        model_used="deepseek-v3",
        prompt_version="report_ai_v1_abc123",
    )
    db_session.add(report)
    await db_session.flush()
    report_id = report.id

    await db_session.delete(source)
    await db_session.flush()

    result = await db_session.execute(select(Report).where(Report.id == report_id))
    assert result.scalar_one_or_none() is None, "Report must be CASCADE deleted with Source"


@pytest.mark.integration
async def test_delete_source_cascades_to_processing_jobs(db_session):
    """CASCADE: deleting a Source deletes all its ProcessingJobs."""
    source = make_source()
    db_session.add(source)
    await db_session.flush()

    job = ProcessingJob(source_id=source.id, status="pending")
    db_session.add(job)
    await db_session.flush()
    job_id = job.id

    await db_session.delete(source)
    await db_session.flush()

    result = await db_session.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    assert result.scalar_one_or_none() is None, "ProcessingJob must be CASCADE deleted with Source"


@pytest.mark.integration
async def test_delete_chat_session_cascades_to_messages(db_session):
    """CASCADE: deleting a ChatSession deletes all its ChatMessages."""
    chat = ChatSession(title="Test chat session")
    db_session.add(chat)
    await db_session.flush()

    message = ChatMessage(
        session_id=chat.id,
        role="user",
        content="What AI tools were covered this week?",
    )
    db_session.add(message)
    await db_session.flush()
    message_id = message.id

    await db_session.delete(chat)
    await db_session.flush()

    result = await db_session.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    assert result.scalar_one_or_none() is None, "ChatMessage must be CASCADE deleted with ChatSession"


@pytest.mark.integration
async def test_delete_knowledge_entry_cascades_to_chunks(db_session):
    """CASCADE: deleting a KnowledgeEntry deletes all its KnowledgeChunks."""
    source = make_source()
    db_session.add(source)
    await db_session.flush()

    entry = KnowledgeEntry(
        source_id=source.id,
        domain=DomainEnum.ai_solutions,
        title="Retrieval-Augmented Generation Patterns",
    )
    db_session.add(entry)
    await db_session.flush()

    chunk = KnowledgeChunk(
        knowledge_entry_id=entry.id,
        chunk_index=0,
        chunk_text="RAG combines dense retrieval with generative models for grounded responses.",
        domain=DomainEnum.ai_solutions,
    )
    db_session.add(chunk)
    await db_session.flush()
    chunk_id = chunk.id

    await db_session.delete(entry)
    await db_session.flush()

    result = await db_session.execute(select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id))
    assert result.scalar_one_or_none() is None, "KnowledgeChunk must be CASCADE deleted with KnowledgeEntry"


# ── vector / tsvector columns ──────────────────────────────────────────────────

@pytest.mark.integration
async def test_knowledge_chunk_accepts_768d_embedding(db_session):
    """TC-3: knowledge_chunks.embedding accepts a 768-dimensional vector (nomic-embed-text shape)."""
    source = make_source()
    db_session.add(source)
    await db_session.flush()

    entry = KnowledgeEntry(
        source_id=source.id,
        domain=DomainEnum.dev_tooling,
        title="Docker Compose Local Dev Setup",
    )
    db_session.add(entry)
    await db_session.flush()

    chunk = KnowledgeChunk(
        knowledge_entry_id=entry.id,
        chunk_index=0,
        chunk_text="Docker Compose orchestrates multi-container local development environments.",
        domain=DomainEnum.dev_tooling,
    )
    db_session.add(chunk)
    await db_session.flush()

    vector_literal = "[" + ",".join(["0.01"] * 768) + "]"
    await db_session.execute(
        text("UPDATE knowledge_chunks SET embedding = CAST(:vec AS vector(768)) WHERE id = :id"),
        {"vec": vector_literal, "id": str(chunk.id)},
    )
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT vector_dims(embedding) FROM knowledge_chunks WHERE id = :id"),
        {"id": str(chunk.id)},
    )
    dims = result.scalar_one()
    assert dims == 768, f"Expected 768-dim embedding, got {dims}"


@pytest.mark.integration
async def test_knowledge_chunk_tsvector_auto_populated(db_session):
    """tsvector GENERATED column is auto-populated from chunk_text on insert."""
    source = make_source()
    db_session.add(source)
    await db_session.flush()

    entry = KnowledgeEntry(
        source_id=source.id,
        domain=DomainEnum.business_dev,
        title="Community Growth Tactics",
    )
    db_session.add(entry)
    await db_session.flush()

    chunk = KnowledgeChunk(
        knowledge_entry_id=entry.id,
        chunk_index=0,
        chunk_text="Consistent engagement and value delivery drive community growth.",
        domain=DomainEnum.business_dev,
    )
    db_session.add(chunk)
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT search_text IS NOT NULL FROM knowledge_chunks WHERE id = :id"),
        {"id": str(chunk.id)},
    )
    assert result.scalar_one() is True, "search_text tsvector should be auto-populated from chunk_text"


@pytest.mark.integration
async def test_tsvector_keyword_search_finds_chunk(db_session):
    """DR-2: tsvector column supports @@ keyword search via to_tsquery."""
    source = make_source()
    db_session.add(source)
    await db_session.flush()

    entry = KnowledgeEntry(
        source_id=source.id,
        domain=DomainEnum.ai_solutions,
        title="Embeddings and Semantic Search",
    )
    db_session.add(entry)
    await db_session.flush()

    chunk = KnowledgeChunk(
        knowledge_entry_id=entry.id,
        chunk_index=0,
        chunk_text="Semantic search uses vector embeddings from transformer models to find relevant content.",
        domain=DomainEnum.ai_solutions,
    )
    db_session.add(chunk)
    await db_session.flush()

    result = await db_session.execute(
        text(
            "SELECT id FROM knowledge_chunks "
            "WHERE id = :id AND search_text @@ to_tsquery('english', 'semantic & search')"
        ),
        {"id": str(chunk.id)},
    )
    assert result.fetchone() is not None, "tsvector search should match 'semantic & search'"


# ── business requirements ──────────────────────────────────────────────────────

@pytest.mark.integration
async def test_report_stores_model_used_and_prompt_version(db_session):
    """BR-2: model_used and prompt_version must persist on Report (required for Tier 3 evolution)."""
    source = make_source()
    db_session.add(source)
    await db_session.flush()

    report = Report(
        source_id=source.id,
        report_type=ReportType.domain_specific,
        domain=DomainEnum.ai_solutions,
        title="AI Tooling Weekly Digest",
        model_used="deepseek-v3",
        prompt_version="report_ai_v2_f3a9bc",
    )
    db_session.add(report)
    await db_session.flush()

    result = await db_session.execute(select(Report).where(Report.id == report.id))
    fetched = result.scalar_one()

    assert fetched.model_used == "deepseek-v3"
    assert fetched.prompt_version == "report_ai_v2_f3a9bc"
