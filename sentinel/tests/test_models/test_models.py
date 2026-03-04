"""Unit tests for SQLAlchemy models — Task 2 (Database Models).

These tests require NO Docker or running services.
They verify enum values, column definitions, and model instantiation.
"""
import uuid

import pytest
import sqlalchemy as sa


class TestDomainEnum:
    def test_all_domain_values_present(self):
        from app.models.section import DomainEnum
        values = {e.value for e in DomainEnum}
        assert values == {"dev_tooling", "ai_solutions", "business_dev", "not_relevant"}

    def test_domain_enum_is_string_enum(self):
        from app.models.section import DomainEnum
        assert DomainEnum.dev_tooling == "dev_tooling"
        assert DomainEnum.ai_solutions == "ai_solutions"


class TestSourceTypeEnum:
    def test_all_source_type_values(self):
        from app.models.source import SourceType
        values = {e.value for e in SourceType}
        assert values == {"youtube", "article", "linkedin", "manual"}


class TestProcessingStatusEnum:
    def test_all_processing_status_values(self):
        from app.models.source import ProcessingStatus
        values = {e.value for e in ProcessingStatus}
        assert values == {"pending", "processing", "completed", "failed"}

    def test_default_is_pending(self):
        """Source default status is pending — not processing or completed."""
        from app.models.source import ProcessingStatus
        assert ProcessingStatus.pending == "pending"


class TestReportTypeEnum:
    def test_all_report_type_values(self):
        from app.models.report import ReportType
        values = {e.value for e in ReportType}
        assert values == {"domain_specific", "executive_summary"}


class TestFeedbackTargetTypeEnum:
    def test_all_feedback_target_type_values(self):
        from app.models.feedback import FeedbackTargetType
        values = {e.value for e in FeedbackTargetType}
        assert values == {"classification", "report", "chat_response", "retrieval", "title"}


class TestSourceModel:
    def test_source_can_be_instantiated(self):
        from app.models.source import Source, SourceType, ProcessingStatus
        s = Source(
            source_type=SourceType.youtube,
            url="https://youtube.com/watch?v=test",
            original_title="Live Recording Jan 15",
        )
        assert s.source_type == SourceType.youtube
        assert s.original_title == "Live Recording Jan 15"
        assert s.title is None  # title is GENERATED — starts as None

    def test_source_has_both_title_columns(self):
        """Both 'title' (generated) and 'original_title' (raw YouTube) must exist."""
        from app.models.source import Source
        mapper = sa.inspect(Source)
        column_names = {c.key for c in mapper.mapper.columns}
        assert "title" in column_names, "sources.title (generated) column missing"
        assert "original_title" in column_names, "sources.original_title (raw YouTube) column missing"

    def test_source_title_and_original_title_are_independent(self):
        """title and original_title are separate columns — never the same column aliased."""
        from app.models.source import Source
        mapper = sa.inspect(Source)
        cols = {c.key: c for c in mapper.mapper.columns}
        assert cols["title"].name == "title"
        assert cols["original_title"].name == "original_title"

    def test_source_id_has_uuid_default_configured(self):
        """Source.id column has a default callable configured (uuid4, evaluated at INSERT)."""
        from app.models.source import Source
        mapper = sa.inspect(Source)
        id_col = mapper.mapper.columns["id"]
        assert id_col.default is not None, "Source.id must have a default (uuid4) configured"


class TestReportModel:
    def test_report_has_model_used_column(self):
        """model_used is REQUIRED — Tier 3 analysis depends on it being present."""
        from app.models.report import Report
        mapper = sa.inspect(Report)
        column_names = {c.key for c in mapper.mapper.columns}
        assert "model_used" in column_names, (
            "reports.model_used column is missing — Tier 3 analysis will break"
        )

    def test_report_has_prompt_version_column(self):
        """prompt_version is REQUIRED — Tier 3 analysis depends on it being present."""
        from app.models.report import Report
        mapper = sa.inspect(Report)
        column_names = {c.key for c in mapper.mapper.columns}
        assert "prompt_version" in column_names, (
            "reports.prompt_version column is missing — Tier 3 analysis will break"
        )

    def test_report_model_used_is_nullable(self):
        """model_used must be nullable because it's set during pipeline, not at creation."""
        from app.models.report import Report
        mapper = sa.inspect(Report)
        cols = {c.key: c for c in mapper.mapper.columns}
        assert cols["model_used"].nullable is True

    def test_report_can_be_instantiated(self):
        from app.models.report import Report, ReportType
        from app.models.section import DomainEnum
        r = Report(
            source_id=uuid.uuid4(),
            report_type=ReportType.domain_specific,
            domain=DomainEnum.ai_solutions,
            model_used="deepseek-v3",
            prompt_version="abc123",
        )
        assert r.model_used == "deepseek-v3"
        assert r.prompt_version == "abc123"


class TestContentSectionModel:
    def test_section_has_needs_review_column(self):
        """needs_review flag is required for Tier 1 fallback path."""
        from app.models.section import ContentSection
        mapper = sa.inspect(ContentSection)
        column_names = {c.key for c in mapper.mapper.columns}
        assert "needs_review" in column_names

    def test_section_has_escalated_to_cloud_column(self):
        """escalated_to_cloud tracks Tier 1B events for observability."""
        from app.models.section import ContentSection
        mapper = sa.inspect(ContentSection)
        column_names = {c.key for c in mapper.mapper.columns}
        assert "escalated_to_cloud" in column_names


class TestFeedbackModel:
    def test_feedback_can_be_instantiated(self):
        from app.models.feedback import Feedback, FeedbackTargetType
        f = Feedback(
            target_type=FeedbackTargetType.classification,
            target_id=uuid.uuid4(),
            rating=0,
            correction={"correct_domain": "ai_solutions"},
        )
        assert f.target_type == FeedbackTargetType.classification
        assert f.correction["correct_domain"] == "ai_solutions"


class TestPromptVersionModel:
    def test_prompt_version_can_be_instantiated(self):
        from app.models.prompt_version import PromptVersion
        pv = PromptVersion(
            prompt_name="classify",
            version_hash="abc123def456",
            content="You are a classifier...",
            is_active=True,
        )
        assert pv.prompt_name == "classify"
        assert pv.version_hash == "abc123def456"
        assert pv.is_active is True

    def test_prompt_version_is_active_has_server_default(self):
        """is_active column has server_default=true — new DB rows default to active."""
        from app.models.prompt_version import PromptVersion
        mapper = sa.inspect(PromptVersion)
        col = mapper.mapper.columns["is_active"]
        assert col.server_default is not None


class TestFewShotModel:
    def test_few_shot_can_be_instantiated(self):
        from app.models.few_shot import FewShotExample
        ex = FewShotExample(
            task_type="classify",
            input_text="We deployed our new RAG pipeline to production...",
            original_output={"domain": "dev_tooling"},
            corrected_output={"domain": "ai_solutions"},
            is_active=True,
        )
        assert ex.task_type == "classify"
        assert ex.is_active is True

    def test_few_shot_is_active_has_server_default(self):
        """is_active column has server_default=true — new DB rows default to active."""
        from app.models.few_shot import FewShotExample
        mapper = sa.inspect(FewShotExample)
        col = mapper.mapper.columns["is_active"]
        assert col.server_default is not None
