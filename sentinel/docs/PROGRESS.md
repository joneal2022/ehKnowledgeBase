# PROGRESS.md — Sentinel Development Log

> **Purpose:** This file survives across sessions and context compactions.
> Claude Code MUST read this at the start of every session.
> Claude Code MUST append to this after every completed task.
>
> Format: Reverse chronological (newest entries at top).

---

## Current State

**Phase:** Phase 1 — Group 2 (Core Services) in progress
**Last Working Session:** 2026-03-03
**Docker Status:** Docker Desktop installed and verified. DB starts with `docker compose up -d db` from `sentinel/`. sentinel_test DB exists and pgvector confirmed working.
**Database:** Migration 0001 applied and verified against sentinel_test. All 11 tables confirmed. pgvector + tsvector columns passing integration tests.
**Git Branch:** group/2-core-services

---

## Session Log

### 2026-03-03 — Tasks 3–5 Complete: YouTube Service, LLM Client, Embedding Service
**What:** Implemented three core services for Group 2. Each followed testing-gate protocol (write → test → commit).
**Files:**
- `app/services/youtube.py` — `YouTubeService.extract()`: video ID parsing (4 URL formats), transcript fetch via `youtube-transcript-api` v0.6+ instance API, oembed metadata, `original_title` preserved raw per DR-4
- `tests/test_services/test_youtube.py` — 17 tests covering URL parsing, transcript joining, metadata failure tolerance, BR-1/DR-4 original title rule
- `app/services/llm_client.py` — `LLMClient.complete(task, prompt)`: task routing (LOCAL/CLOUD), `TASK_ROUTING` dict, `parse_llm_json()` with code-fence stripping, model from config only (TC-1), timeouts per task
- `tests/test_services/test_llm_client.py` — 21 tests: JSON parsing, routing table, model-from-config enforcement, unknown task defaults to cloud
- `app/services/embedding.py` — `EmbeddingService` singleton: `embed()`, `embed_batch()`, 768d dimension verify on first call, `DimensionMismatchError`, `get_embedding_service()` factory
- `tests/test_services/test_embedding.py` — 17 tests: vector dimensions, batch, model-from-settings (TC-1), dimension verification once, HTTP/connection error propagation, singleton identity
**Status:** Working — 89 Tier A tests passing
**Notes:**
- youtube-transcript-api v0.6+ uses instance method `api.fetch(video_id)` not class method `get_transcript()` — API breaking change
- Settings patching in embedding tests requires patching `app.services.embedding.settings`, not the module directly
- Tasks 3/4/5 each committed separately on group/2-core-services

---

### 2026-03-03 — Group 1 Complete: Integration Tests + Merge to Main + Doc Reorganisation
**What:** Added Tier B integration tests for Group 1 (16 tests). Updated pyproject.toml with pytest markers. Reorganised all docs from repo root into `sentinel/docs/` and `sentinel/tasks/`. Replaced CLAUDE.md §3.5 with testing-gate skill reference. Installed `testing-gate` skill globally (`~/.claude/commands/`). Merged `group/1-infrastructure` → `main`.
**Files:**
- `sentinel/tests/test_integration/conftest.py` — DB fixture (apply_migrations, db_session with rollback)
- `sentinel/tests/test_integration/test_migration.py` — 5 tests: single head, all tables, pgvector ext, vector(768) type, tsvector column
- `sentinel/tests/test_integration/test_db_models.py` — 11 tests: CRUD, 5 CASCADE deletes, 768d vector insert, tsvector auto-populate, keyword search, BR-2 metadata
- `sentinel/pyproject.toml` — added `markers` + `addopts = "-m 'not integration'"` (Tier A excludes Tier B by default)
- `sentinel/CLAUDE.md` — moved to sentinel/, §3.5 replaced, TEST_CONTEXT.md added to ref map
- `sentinel/docs/` — ARCHITECTURE.md, CODE_PATTERNS.md, REQUIREMENTS.md, PROGRESS.md moved here
- `sentinel/tasks/todo.md` — moved here
- `sentinel/docs/TEST_CONTEXT.md` — created (Sentinel-specific testing context)
- `~/.claude/commands/testing-gate.md` — universal testing skill installed
- `~/.claude/references/TEST_CONTEXT_TEMPLATE.md` — reusable template installed
**Status:** All tests passing — Tier A: 34 passed, Tier B: 16 passed. Merged to main.
**Notes:** Tier B requires Docker DB running (`docker compose up -d db`). Integration test sessions use apply_migrations fixture (downgrade base → upgrade head) then rollback per test. `.env` file must exist (copy from `.env.example`) for docker compose to start.

---

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
