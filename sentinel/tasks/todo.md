# TODO.md — Sentinel Work Plan

> **Purpose:** Claude Code creates and maintains this plan.
> Plans must be verified by the user before work begins.
> Claude Code checks off tasks as they're completed.

---

## Current Phase: Phase 1 — Core Pipeline (MVP)

### Status: Group 6 complete (283 Tier A tests), awaiting Tier B + merge. Phase 1 MVP DONE.

### Current Group

#### Group 2: Core Services
- [x] Task 3 — YouTube extraction service
  - `app/services/youtube.py`
  - `YouTubeService.extract(url)` → returns `{transcript, original_title, author, published_at, url}`
  - Uses `youtube-transcript-api` (no API key needed)
  - Graceful error if captions unavailable
  - Does NOT use generated title — stores original YouTube title as `original_title`

- [x] Task 4 — LLM client abstraction
  - `app/services/llm_client.py`
  - `LLMClient.complete(task, prompt, **kwargs)` — routes to local or cloud based on task
  - Local: Ollama HTTP API (`OLLAMA_LOCAL_URL`)
  - Cloud: Ollama Cloud API (`OLLAMA_CLOUD_URL` + `OLLAMA_CLOUD_API_KEY`)
  - `parse_llm_json(text)` — strips markdown fences, parses JSON, raises `ValueError` on failure
  - All calls use `get_model_for_task()` from config — no hardcoded model strings
  - Timeouts: 30s classification, 120s reports

- [x] Task 5 — Embedding service
  - `app/services/embedding.py`
  - `EmbeddingService` singleton — `get_embedding_service()` factory
  - `embed(text)` → `list[float]` (768d, nomic-embed-text)
  - `embed_batch(texts)` → `list[list[float]]`
  - Verifies 768d on startup or first call — raises if wrong dimension
  - ALWAYS uses `settings.OLLAMA_MODEL_EMBED` — never any other model

- [x] Task 6 — Prompt manager + base prompt files
  - `app/pipeline/prompts/manager.py`
  - `PromptManager.get(prompt_name)` → rendered prompt string
  - `PromptManager.render(prompt_name, few_shot_examples=None, **vars)` → filled template
  - Prompt files: `preprocess.py`, `segment.py`, `classify.py`, `report_dev.py`, `report_ai.py`, `report_biz.py`, `synthesize.py`
  - Each prompt has `{few_shot_examples}` placeholder
  - SHA256 hash for version tracking → saves to `prompt_versions` table on first use

### Blocked

*(nothing)*

---

### Remaining Groups

#### Group 3: Basic UI Shell
- [x] Task 7 — Base HTMX layout + nav (base.html, home page, FastAPI app wired up)
- [x] Task 8 — Add Video form + dashboard feed (URL input, POST endpoint, status polling)

#### Group 4: LangGraph Pipeline ✅ (224 Tier A tests — awaiting Tier B + merge)
- [x] Task 9 — Pipeline state + graph shell (PipelineState TypedDict, graph with node stubs)
- [x] Task 10 — Extract + preprocess nodes (YouTube → DB, local 7B cleanup)
- [x] Task 11 — Segment node (cloud model, JSON sections, stored to content_sections)
- [x] Task 12 — Classify node (local 7B + Tier 1 Loop 1A parse-retry + 1B cloud escalation)
- [x] Task 13 — Domain report nodes (report_dev, report_ai, report_biz — model_used + prompt_version stored)
- [x] Task 14 — Synthesize + title node (single cloud call, updates sources.title)
- [x] Task 15 — Persist results + background worker (Celery task, POST enqueues job)

#### Group 5: Feedback System ✅ (245 Tier A tests — awaiting Tier B + merge)
- [x] Task 16 — Feedback widgets + API (thumbs/stars, correction dropdown, inline title edit)
- [x] Task 17 — Prompt evolution service (Tier 2: few-shot accumulation → prompt rebuild)

#### Group 6: Polish + Observability ✅ (283 Tier A tests — awaiting Tier B + merge)
- [x] Task 18 — Video detail page (domain tabs, report cards, feedback widgets)
- [x] Task 19 — Observability (LangFuse tracing, trace_id in jobs, quality dashboard)
- [x] Task 20 — Polish + domain filter view (skeleton cards, retry button, mobile layout)

---

### Completed

#### Group 1: Infrastructure ✅ (merged to main 2026-03-03)
- [x] Task 1 — Docker Compose (5 services: app, worker, db, redis, ollama) + Dockerfile + .env.example + pyproject.toml
- [x] Task 2 — Database models (11 tables) + Alembic migrations
- [x] Tier A tests: 34 unit tests (models + config)
- [x] Tier B tests: 16 integration tests (migration, CRUD, CASCADE, vector/tsvector)

---

## Review

*(Claude Code adds a review section here after completing a phase)*
