# PROGRESS.md — Sentinel Development Log

> **Purpose:** This file survives across sessions and context compactions.
> Claude Code MUST read this at the start of every session.
> Claude Code MUST append to this after every completed task.
>
> Format: Reverse chronological (newest entries at top).

---

## Current State

**Phase:** Phase 1 — Group 4 (LangGraph Pipeline) COMPLETE — Awaiting Tier B + merge
**Last Working Session:** 2026-03-03
**Docker Status:** Docker Desktop installed and verified. DB starts with `docker compose up -d db` from `sentinel/`. sentinel_test DB exists and pgvector confirmed working.
**Database:** Migration 0001 applied and verified. All 11 tables confirmed.
**Git Branch:** group/4-langgraph-pipeline
**Tests passing:** 224 Tier A (all tasks through Task 15)

### Group 4 — All Tasks Complete
- [x] Task 9: PipelineState TypedDict + build_graph() shell (12 tests)
- [x] Task 10: extract_node + preprocess_node (14 tests)
- [x] Task 11: segment_node (9 tests)
- [x] Task 12: classify_node — Tier 1A + Tier 1B (10 tests)
- [x] Task 13: report_dev/ai/biz nodes — BR-2, TC-1 (12 tests)
- [x] Task 14: synthesize_node — BR-1, DR-4 (6 tests)
- [x] Task 15: persist_node + Celery worker + POST enqueue (6 tests)

**Next step:** Run Tier B integration tests (`docker compose up -d && uv run pytest tests/test_integration/ -v -m integration`), then merge group/4-langgraph-pipeline → main.

### ~~Implementation Plan for Tasks 12-15~~ (COMPLETED 2026-03-03)

**Key patterns already established (do not change):**
- Nodes receive services via `config["configurable"]` dict: `session`, `llm_client`, `youtube_service`
- `PromptManager(session)` used inside each node for prompt + version hash
- `parse_llm_json()` for all LLM JSON output
- `session.add(row)` is SYNC, `session.flush()` is ASYNC — mock accordingly in tests
- All nodes return dict of state field updates (not full state)
- Errors go in `errors: list[str]` (never raise — graceful degradation)
- `prompt_versions: dict[str, str]` accumulates task→hash across nodes

---

**Task 12: classify_node**
File: `app/pipeline/nodes/classify.py`
Input state fields: `sections` (list of dicts from segment_node)
Output state fields: `classified_sections`, `prompt_versions["classify"]`, `errors`

Logic per section:
1. Build prompt: `prompt_manager.get_active_prompt("classify")` → format with section content + `few_shot_examples=""`
2. Call `llm_client.complete("classify", prompt)` → attempt `parse_llm_json(raw)`
3. **Tier 1A** (Loop 1A): if parse fails → retry with `prompt_manager.get_strict_variant("classify")` → attempt parse again → if still fails → set domain="not_relevant", confidence=0.0, needs_review=True, continue
4. **Tier 1B** (Loop 1B): if parsed confidence < 0.6 → call `llm_client.complete("classify_escalation", prompt)` → parse → if cloud result has higher confidence, use it; set `escalated_to_cloud=True`
5. Update ContentSection row in DB: `session.execute(update(ContentSection).where(...).values(domain=..., confidence=..., reasoning=..., needs_review=..., escalated_to_cloud=...))`
6. Append to classified_sections list

Tests must cover:
- Happy path: section gets domain/confidence/reasoning
- Tier 1A: parse fail → strict retry → success
- Tier 1A: parse fail → strict retry → also fails → not_relevant + needs_review=True
- Tier 1B: confidence=0.4 → cloud escalation called; higher cloud confidence used
- Tier 1B: confidence=0.4 → cloud returns lower confidence → local result kept
- Multiple sections processed independently
- prompt_versions["classify"] set
- DB update called for each section

---

**Task 13: report_dev_node, report_ai_node, report_biz_node**
Files: `app/pipeline/nodes/report_dev.py`, `report_ai.py`, `report_biz.py`

Each node is nearly identical — parameterized by domain:
- `report_dev_node`: domain filter = "dev_tooling", prompt = "report_dev", task = "report"
- `report_ai_node`: domain filter = "ai_solutions", prompt = "report_ai", task = "report"
- `report_biz_node`: domain filter = "business_dev", prompt = "report_biz", task = "report"

Logic for each:
1. Filter `state["classified_sections"]` for sections where domain == target_domain
2. If no sections → return `{"reports": {}, "prompt_versions": {}, "errors": []}` (skip)
3. Build sections_text = join section contents
4. Get prompt from PromptManager (e.g., "report_dev") + version_hash
5. Format prompt with `sections_text` + `few_shot_examples=""`
6. Call `llm_client.complete("report", prompt)` → `parse_llm_json(raw)`
7. model_used = `settings.get_model_for_task("report")` (NEVER hardcoded — TC-1)
8. Store Report in DB: `Report(source_id=..., report_type=ReportType.domain_specific, domain=DomainEnum.<domain>, title=..., content=..., key_takeaways=..., action_items=..., relevance_score=..., model_used=model_used, prompt_version=version_hash)`
9. Return `{"reports": {domain: report_dict}, "prompt_versions": {"report_<domain>": version_hash}, "errors": []}`

Note: `reports` dict merges across nodes via LangGraph last-write — each node writes its own domain key.

Tests must cover (per domain node):
- No sections for domain → returns empty, skips LLM call
- Sections present → LLM called with "report" task
- BR-2: model_used and prompt_version are set on Report row
- TC-1: model_used comes from settings.get_model_for_task("report"), not hardcoded
- Report stored in DB (session.add called once)
- Parse failure → error returned, no DB write

---

**Task 14: synthesize_node**
File: `app/pipeline/nodes/synthesize.py`
Input state: `reports` (dict), `original_title`
Output: `synthesis` (dict), `prompt_versions["synthesize"]`, `errors`

Logic:
1. Build `domain_reports_text` from state["reports"] — for each domain, format title + summary
2. Get prompt "synthesize" from PromptManager; format with `original_title`, `domain_reports_text`, `few_shot_examples=""`
3. Call `llm_client.complete("synthesize", prompt)` → `parse_llm_json(raw)`
4. Expected JSON: `{"title": "...", "tldr": "...", "dont_miss": "...", "domain_breakdown": {...}}`
5. Update Source.title = synthesis["title"] in DB (NOT original_title — BR-1, DR-4)
6. Return `{"synthesis": parsed_data, "prompt_versions": {"synthesize": version_hash}, "errors": []}`

Tests must cover:
- BR-1/DR-4: Source.title updated to generated title (NOT original_title)
- synthesis dict has title, tldr, dont_miss, domain_breakdown keys
- No reports → graceful empty synthesis (still runs with empty domain_reports_text)
- prompt_versions["synthesize"] recorded
- Parse failure → error, no DB update to title

---

**Task 15: persist_node + Celery worker + POST endpoint update**

**persist_node** (`app/pipeline/nodes/persist.py`):
1. Update Source.processing_status = ProcessingStatus.completed
2. `await session.flush()`
3. Return `{"errors": []}`
(Errors accumulated in state["errors"] throughout pipeline — persist marks completion regardless)

**Celery worker** (`app/workers/__init__.py`, `app/workers/tasks.py`):
```python
# app/workers/tasks.py
import asyncio
from celery import Celery
from app.config import settings

celery_app = Celery("sentinel", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.task_serializer = "json"

@celery_app.task(name="run_pipeline", bind=True)
def run_pipeline(self, source_id: str) -> dict:
    return asyncio.run(_run_async(self.request.id, source_id))

async def _run_async(celery_task_id: str, source_id: str) -> dict:
    from app.database import async_session_factory
    from app.pipeline.graph import get_compiled_graph
    from app.services.llm_client import LLMClient
    from app.services.youtube import YouTubeService
    from app.models.source import Source
    from sqlalchemy import select

    graph = get_compiled_graph()
    llm_client = LLMClient()
    youtube_svc = YouTubeService()

    async with async_session_factory() as session:
        result = await session.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one()
        initial_state = {
            "source_id": source_id, "url": source.url,
            "transcript": "", "original_title": None, "author": None,
            "preprocessed_transcript": "", "sections": [], "classified_sections": [],
            "reports": {}, "synthesis": {}, "errors": [], "prompt_versions": {},
        }
        config = {"configurable": {"session": session, "llm_client": llm_client, "youtube_service": youtube_svc}}
        final_state = await graph.ainvoke(initial_state, config=config)
        await session.commit()
        return {"status": "completed", "errors": final_state.get("errors", [])}
```

**Updated POST /api/sources/youtube** (`app/api/sources.py`):
- After creating Source → create `ProcessingJob(source_id=source.id, status="queued")`
- After commit → call `run_pipeline.delay(str(source.id))`
- Update `job.celery_task_id = task_result.id; await session.commit()`

Tests for Task 15:
- persist_node sets Source.processing_status = completed
- persist_node calls session.flush
- run_pipeline task is registered on celery_app
- POST /api/sources/youtube calls run_pipeline.delay (mock the import)
- POST creates a ProcessingJob record

---

## Session Log

### 2026-03-03 — Tasks 12–15 Complete: Full LangGraph Pipeline Implemented
**What:** Implemented all remaining Group 4 pipeline nodes. Full pipeline is now wired end-to-end.
**Files:**
- `app/pipeline/nodes/classify.py` — classify_node: Tier 1A (parse-fail → strict retry) + Tier 1B (low confidence → cloud escalation); DB UPDATE per section
- `app/pipeline/nodes/_report_base.py` — shared `generate_domain_report()` helper
- `app/pipeline/nodes/report_dev.py`, `report_ai.py`, `report_biz.py` — domain report nodes; BR-2 (model_used + prompt_version stored); TC-1 (model from settings)
- `app/pipeline/nodes/synthesize.py` — executive summary + generated title; updates Source.title via DB UPDATE (BR-1, DR-4)
- `app/pipeline/nodes/persist.py` — marks Source.processing_status=completed
- `app/workers/__init__.py`, `app/workers/tasks.py` — Celery app + `run_pipeline` task (asyncio.run wrapper)
- `app/api/sources.py` — POST endpoint updated: creates ProcessingJob, enqueues run_pipeline.delay()
- Tests: 43 new tests across tasks 12-15 (10 + 12 + 6 + 3 + 6 + 6 = 43 total)
**Status:** 224 Tier A tests passing. Awaiting Tier B + merge.
**Notes:**
- Tier 1A: first local call → parse_llm_json fails → retry with strict_variant prompt → if still fails → not_relevant + needs_review=True
- Tier 1B: parsed confidence < 0.6 → classify_escalation (cloud) → if cloud higher confidence, use cloud result + escalated_to_cloud=True
- _report_base.py shared helper avoids duplication across 3 nearly-identical nodes
- run_pipeline import moved to top of sources.py (not lazy) for proper test patching
- Existing test_sources.py POST tests updated to mock run_pipeline.delay (avoids Redis connection)

---

### 2026-03-03 — Tasks 7–8 Complete: HTMX UI Shell + Add Video Form
**What:** Wired up FastAPI app, base layout, and the Add Video → dashboard feed flow.
**Files:**
- `app/main.py` — FastAPI app with lifespan, static mount, routers
- `app/templates_env.py` — Jinja2Templates singleton
- `app/pages/dashboard.py` — `GET /` (dashboard), `GET /sources/feed` (HTMX fragment)
- `app/api/sources.py` — `POST /api/sources/youtube` (202 + HX-Trigger), `GET /api/sources`
- `app/schemas/source.py` — `YouTubeSubmitRequest` (YouTube URL validation), `SourceResponse`
- `app/templates/base.html` — HTMX 2.0.4, Tailwind CDN, hx-boost
- `app/templates/components/nav.html` — Sentinel brand + Dashboard/Knowledge/Chat/Quality links
- `app/templates/pages/dashboard.html` — Add Video form (hx-post) + source list (hx-trigger=refreshSources)
- `app/templates/components/video_card.html` — title/url/author/status card
- `app/templates/components/processing_status.html` — status badge (queued/processing/done/failed); processing card auto-polls every 5s
- `app/templates/fragments/source_list.html` — empty state or list of cards
- `tests/test_api/test_dashboard.py` — 12 tests (page routes)
- `tests/test_api/test_sources.py` — 16 tests (schema validation, POST 202, HX-Trigger header, GET list)
**Status:** Working — 155 Tier A tests passing
**Notes:**
- POST returns `HX-Trigger: refreshSources` header; source list div listens with `hx-trigger="load, refreshSources from:body"`
- Processing status badge on in-progress cards uses `hx-trigger="every 5s"` to poll the feed endpoint
- No actual Celery task yet — source is created as `pending` and stays there until Group 4

---

### 2026-03-03 — Task 6 Complete: Prompt Manager + Base Prompt Files
**What:** Implemented `PromptManager` with SHA256 versioning and first-use DB persistence. Created 7 prompt template files for all pipeline nodes.
**Files:**
- `app/pipeline/prompts/__init__.py` — package init
- `app/pipeline/prompts/manager.py` — `PromptManager(session)`: `get_active_prompt()`, `get_prompt_version_hash()`, `get_strict_variant()`, `_save_base_prompt()`, `_load_base_prompt()`, `STRICT_SUFFIX`, `KNOWN_PROMPTS`
- `app/pipeline/prompts/preprocess.py` — caption cleanup prompt
- `app/pipeline/prompts/segment.py` — topical section splitting prompt (JSON array output)
- `app/pipeline/prompts/classify.py` — domain classification prompt (matches CODE_PATTERNS.md example)
- `app/pipeline/prompts/report_dev.py` — Dev/Tooling report prompt with business context
- `app/pipeline/prompts/report_ai.py` — AI Solutions report prompt with business context
- `app/pipeline/prompts/report_biz.py` — Business Dev report prompt with business context
- `app/pipeline/prompts/synthesize.py` — Executive summary + title generation (matches CODE_PATTERNS.md)
- `tests/test_pipeline/test_prompt_manager.py` — 38 tests: TC-5 all 7 files have `{few_shot_examples}`, DB-hit/miss behaviour, first-use save, SHA256 hash, strict variant, import error
**Status:** Working — 127 Tier A tests passing
**Notes:**
- `get_active_prompt()` on first use saves base template to `prompt_versions` and returns it; second call finds it in DB
- `get_prompt_version_hash()` returns `"base"` before any DB version exists
- All report prompts include `BUSINESS_CONTEXT` preamble (15-dev shop, Louisiana, Dallas/Houston)
- All 7 prompt files verified to have `{few_shot_examples}` placeholder (TC-5)

---

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
