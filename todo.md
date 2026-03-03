# TODO.md — Sentinel Work Plan

> **Purpose:** Claude Code creates and maintains this plan.
> Plans must be verified by the user before work begins.
> Claude Code checks off tasks as they're completed.

---

## Current Phase: Phase 1 — Core Pipeline (MVP)

### Status: In Progress

### Tasks

#### Group 1: Infrastructure
- [ ] Task 1 — Docker Compose (5 services: app, worker, db, redis, ollama) + Dockerfile + .env.example + pyproject.toml
- [ ] Task 2 — Database models (11 tables) + Alembic migrations

#### Group 2: Core Services
- [ ] Task 3 — YouTube extraction service (youtube-transcript-api, no API key)
- [ ] Task 4 — LLM client abstraction (local/cloud routing, parse_llm_json)
- [ ] Task 5 — Embedding service (singleton, 768d verification)
- [ ] Task 6 — Prompt manager (versioning, few-shot injection) + base prompt files

#### Group 3: Basic UI Shell
- [ ] Task 7 — Base HTMX layout + nav (base.html, home page, FastAPI app wired up)
- [ ] Task 8 — Add Video form + dashboard feed (URL input, POST endpoint, status polling)

#### Group 4: LangGraph Pipeline
- [ ] Task 9 — Pipeline state + graph shell (PipelineState TypedDict, graph with node stubs)
- [ ] Task 10 — Extract + preprocess nodes (YouTube → DB, local 7B cleanup)
- [ ] Task 11 — Segment node (cloud model, JSON sections, stored to content_sections)
- [ ] Task 12 — Classify node (local 7B + Tier 1 Loop 1A parse-retry + 1B cloud escalation)
- [ ] Task 13 — Domain report nodes (report_dev, report_ai, report_biz — model_used + prompt_version stored)
- [ ] Task 14 — Synthesize + title node (single cloud call, updates sources.title)
- [ ] Task 15 — Persist results + background worker (Celery task, POST enqueues job)

#### Group 5: Feedback System
- [ ] Task 16 — Feedback widgets + API (thumbs/stars, correction dropdown, inline title edit)
- [ ] Task 17 — Prompt evolution service (Tier 2: few-shot accumulation → prompt rebuild)

#### Group 6: Polish + Observability
- [ ] Task 18 — Video detail page (domain tabs, report cards, feedback widgets)
- [ ] Task 19 — Observability (LangFuse tracing, trace_id in jobs, quality dashboard)
- [ ] Task 20 — Polish + domain filter view (skeleton cards, retry button, mobile layout)

### Blocked

*(nothing)*

### Completed

*(nothing yet)*

---

## Review

*(Claude Code adds a review section here after completing a phase)*
