# PROGRESS.md — Sentinel Development Log

> **Purpose:** This file survives across sessions and context compactions.
> Claude Code MUST read this at the start of every session.
> Claude Code MUST append to this after every completed task.
>
> Format: Reverse chronological (newest entries at top).

---

## Current State

**Phase:** Phase 1 — Group 1 (Infrastructure) complete, tests passing
**Last Working Session:** 2026-03-02
**Docker Status:** Not yet started (docker compose up not run — services defined, not running)
**Database:** Migration written (0001_initial_schema.py) — not yet applied (needs Docker up)
**Git Branch:** group/1-infrastructure

---

## Session Log

### 2026-03-02 — Test Retrofit + CLAUDE.md Testing Rules
**What:** Retrofitted missing tests for Tasks 1 & 2 (per CLAUDE.md §3 "test before commit" rule that was skipped). Updated CLAUDE.md with explicit §3.5 Testing Requirements section defining two test tiers (unit vs integration) and per-task-type test expectations.
**Files:**
- `CLAUDE.md` — added §3.5 Testing Requirements
- `sentinel/tests/conftest.py` — shared test fixtures
- `sentinel/tests/test_services/test_config.py` — 12 unit tests for config/routing
- `sentinel/tests/test_models/test_models.py` — 22 unit tests for all models
- `sentinel/tests/fixtures/sample_transcript.txt` — sample transcript for future pipeline tests
- `sentinel/app/models/section.py` — added Python-side `default=False` to boolean columns
- `sentinel/app/models/prompt_version.py` — added `default=True` to is_active
- `sentinel/app/models/few_shot.py` — added `default=True` to is_active
**Status:** Working — 34/34 tests passing
**Environment:** uv venv active, no Docker needed for unit tests
**Notes:** SA 2.0 `default=` in `mapped_column` is INSERT-time only, not Python construction-time. Tests for boolean defaults now verify `server_default` metadata rather than instantiation behavior. UUID generation also happens at INSERT time.

---

### 2026-03-02 — Task 2: Database Models + Alembic Migration
**What:** Created all 11 SQLAlchemy ORM models and hand-written Alembic migration (0001_initial_schema.py) covering all tables, enums, pgvector extension, and tsvector generated column.
**Files:**
- `sentinel/app/config.py` — pydantic-settings with `get_model_for_task()` helper
- `sentinel/app/database.py` — async SQLAlchemy engine + session factory
- `sentinel/app/models/` — 11 model files: source, section, report, knowledge, chat, job, feedback, prompt_version, few_shot + `__init__.py`
- `sentinel/alembic/env.py` — configured with auto-discovery of all models
- `sentinel/alembic/versions/0001_initial_schema.py` — creates all tables + pgvector + tsvector
**Status:** Working — migration parses cleanly (`alembic heads` = 0001). Not yet applied to DB.
**Environment:** uv venv with all 113 packages installed
**Notes:** knowledge_chunks vector(768) and tsvector columns added via raw DDL (pgvector not in SQLAlchemy Column type).

---

### 2026-03-02 — Task 1: Docker Compose + Infrastructure
**What:** Created all Docker infrastructure files for the 5-service sentinel application.
**Files:**
- `sentinel/docker-compose.yml` — 5 services: app, worker, scheduler, db (pgvector:pg16), redis:7-alpine, ollama
- `sentinel/Dockerfile` — Python 3.12-slim
- `sentinel/.env.example` — all env vars from ARCHITECTURE.md
- `sentinel/pyproject.toml` — uv-compatible (hatchling build), all dependencies listed
- `sentinel/.gitignore`
**Status:** Working — files created, not yet run
**Environment:** uv selected over pip per user preference; uv sync installed 113 packages
**Notes:** Used `uv` (not pip) for package management. `.venv` created at `sentinel/.venv`.
