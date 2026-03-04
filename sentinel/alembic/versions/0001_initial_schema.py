"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── ENUMS ──────────────────────────────────────────────────────────────────
    source_type_enum = postgresql.ENUM(
        "youtube", "article", "linkedin", "manual",
        name="sourcetype", create_type=False,
    )
    processing_status_enum = postgresql.ENUM(
        "pending", "processing", "completed", "failed",
        name="processingstatus", create_type=False,
    )
    domain_enum = postgresql.ENUM(
        "dev_tooling", "ai_solutions", "business_dev", "not_relevant",
        name="domainenum", create_type=False,
    )
    report_type_enum = postgresql.ENUM(
        "domain_specific", "executive_summary",
        name="reporttype", create_type=False,
    )
    approval_status_enum = postgresql.ENUM(
        "pending_report", "approved_for_education",
        "pending_education_review", "approved", "rejected",
        name="approvalstatus", create_type=False,
    )
    feedback_target_type_enum = postgresql.ENUM(
        "classification", "report", "chat_response", "retrieval", "title",
        name="feedbacktargettype", create_type=False,
    )

    op.execute("CREATE TYPE sourcetype AS ENUM ('youtube','article','linkedin','manual')")
    op.execute("CREATE TYPE processingstatus AS ENUM ('pending','processing','completed','failed')")
    op.execute("CREATE TYPE domainenum AS ENUM ('dev_tooling','ai_solutions','business_dev','not_relevant')")
    op.execute("CREATE TYPE reporttype AS ENUM ('domain_specific','executive_summary')")
    op.execute("CREATE TYPE approvalstatus AS ENUM ('pending_report','approved_for_education','pending_education_review','approved','rejected')")
    op.execute("CREATE TYPE feedbacktargettype AS ENUM ('classification','report','chat_response','retrieval','title')")

    # ── sources ────────────────────────────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("original_title", sa.Text, nullable=True),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_content", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("processing_status", processing_status_enum, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── content_sections ───────────────────────────────────────────────────────
    op.create_table(
        "content_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("start_timestamp", sa.Text, nullable=True),
        sa.Column("end_timestamp", sa.Text, nullable=True),
        sa.Column("domain", domain_enum, nullable=True),
        sa.Column("classification_confidence", sa.Float, nullable=True),
        sa.Column("classification_reasoning", sa.Text, nullable=True),
        sa.Column("needs_review", sa.Boolean, server_default="false"),
        sa.Column("escalated_to_cloud", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── reports ────────────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", report_type_enum, nullable=False),
        sa.Column("domain", domain_enum, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("key_takeaways", postgresql.JSONB, nullable=True),
        sa.Column("action_items", postgresql.JSONB, nullable=True),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column("model_used", sa.Text, nullable=True),
        sa.Column("prompt_version", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── knowledge_entries ──────────────────────────────────────────────────────
    op.create_table(
        "knowledge_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("domain", domain_enum, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("original_content", sa.Text, nullable=True),
        sa.Column("educational_content", sa.Text, nullable=True),
        sa.Column("approval_status", approval_status_enum, nullable=False, server_default="pending_report"),
        sa.Column("approved_by", sa.Text, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── knowledge_chunks ───────────────────────────────────────────────────────
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("context_summary", sa.Text, nullable=True),
        sa.Column("domain", domain_enum, nullable=False),
        sa.Column("source_title", sa.Text, nullable=True),
        sa.Column("section_title", sa.Text, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Add vector and tsvector columns via raw DDL (pgvector type not in SQLAlchemy Column)
    op.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding vector(768)")
    op.execute("ALTER TABLE knowledge_chunks ADD COLUMN search_text tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(chunk_text, ''))) STORED")
    op.execute("CREATE INDEX knowledge_chunks_embedding_idx ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX knowledge_chunks_search_text_idx ON knowledge_chunks USING gin (search_text)")

    # ── chat_sessions ──────────────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── chat_messages ──────────────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources_used", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── processing_jobs ────────────────────────────────────────────────────────
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("celery_task_id", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── feedback ───────────────────────────────────────────────────────────────
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_type", feedback_target_type_enum, nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("correction", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── prompt_versions ────────────────────────────────────────────────────────
    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prompt_name", sa.Text, nullable=False),
        sa.Column("version_hash", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("few_shot_examples", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performance_metrics", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── few_shot_bank ──────────────────────────────────────────────────────────
    op.create_table(
        "few_shot_bank",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_type", sa.Text, nullable=False),
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("original_output", postgresql.JSONB, nullable=True),
        sa.Column("corrected_output", postgresql.JSONB, nullable=False),
        sa.Column("source_feedback_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feedback.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("few_shot_bank")
    op.drop_table("prompt_versions")
    op.drop_table("feedback")
    op.drop_table("processing_jobs")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_entries")
    op.drop_table("reports")
    op.drop_table("content_sections")
    op.drop_table("sources")
    op.execute("DROP TYPE IF EXISTS feedbacktargettype")
    op.execute("DROP TYPE IF EXISTS approvalstatus")
    op.execute("DROP TYPE IF EXISTS reporttype")
    op.execute("DROP TYPE IF EXISTS domainenum")
    op.execute("DROP TYPE IF EXISTS processingstatus")
    op.execute("DROP TYPE IF EXISTS sourcetype")
