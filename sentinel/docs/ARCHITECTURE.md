# ARCHITECTURE.md — Sentinel Technical Architecture

> This file is the technical reference for project structure, database schema, model routing, and infrastructure.
> For workflow rules → `CLAUDE.md`
> For code examples → `docs/CODE_PATTERNS.md`
> For full requirements → `docs/REQUIREMENTS.md`

---

## 1. Project Structure

```
sentinel/
├── CLAUDE.md                  # Workflow rules (READ FIRST every session)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── docs/
│   ├── ARCHITECTURE.md        # THIS FILE
│   ├── CODE_PATTERNS.md       # Implementation examples
│   ├── REQUIREMENTS.md        # Full requirements
│   └── PROGRESS.md            # Session-surviving progress log
├── tasks/
│   └── todo.md                # Current work plan
├── alembic/
│   ├── alembic.ini
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # pydantic-settings
│   ├── database.py            # Async PostgreSQL (asyncpg + SQLAlchemy)
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── source.py
│   │   ├── section.py
│   │   ├── report.py
│   │   ├── knowledge.py
│   │   ├── chat.py
│   │   ├── job.py
│   │   ├── feedback.py
│   │   ├── prompt_version.py
│   │   └── few_shot.py
│   ├── schemas/               # Pydantic request/response schemas
│   ├── api/                   # JSON API routes
│   │   ├── sources.py
│   │   ├── reports.py
│   │   ├── knowledge.py
│   │   ├── chat.py
│   │   └── feedback.py
│   ├── pages/                 # HTMX page routes (return HTML)
│   │   ├── dashboard.py
│   │   ├── video_detail.py
│   │   ├── domain_view.py
│   │   ├── knowledge.py
│   │   ├── chat.py
│   │   └── quality.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── components/
│   │   │   ├── video_card.html
│   │   │   ├── report_card.html
│   │   │   ├── approval_buttons.html
│   │   │   ├── feedback_widget.html
│   │   │   ├── inline_title_edit.html
│   │   │   ├── processing_status.html
│   │   │   ├── chat_message.html
│   │   │   └── nav.html
│   │   ├── pages/
│   │   │   ├── dashboard.html
│   │   │   ├── video_detail.html
│   │   │   ├── domain_view.html
│   │   │   ├── knowledge.html
│   │   │   ├── chat.html
│   │   │   └── quality.html
│   │   └── fragments/         # HTMX partial responses
│   ├── pipeline/
│   │   ├── graph.py           # LangGraph graph definition
│   │   ├── state.py           # Pipeline state schema
│   │   ├── nodes/
│   │   │   ├── extract.py     # YouTube transcript extraction
│   │   │   ├── preprocess.py  # Caption cleanup (local 7B)
│   │   │   ├── segment.py     # Topical segmentation (cloud)
│   │   │   ├── classify.py    # Domain classification (local 7B + Tier 1 escalation)
│   │   │   ├── report_dev.py  # Dev/Tooling report (cloud)
│   │   │   ├── report_ai.py   # AI Solutions report (cloud)
│   │   │   ├── report_biz.py  # Business Dev report (cloud)
│   │   │   ├── synthesize.py  # Executive summary + title generation (cloud)
│   │   │   ├── educate.py     # Education transformation (cloud, Phase 2)
│   │   │   └── embed.py       # Contextual chunking + embedding (local, Phase 2)
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── manager.py     # Prompt versioning + few-shot injection
│   │       ├── preprocess.py
│   │       ├── segment.py
│   │       ├── classify.py    # Has {few_shot_examples} placeholder
│   │       ├── report_dev.py
│   │       ├── report_ai.py
│   │       ├── report_biz.py
│   │       ├── synthesize.py  # Includes title generation
│   │       └── educate.py
│   ├── services/
│   │   ├── youtube.py         # youtube-transcript-api wrapper
│   │   ├── llm_client.py      # Local + cloud routing (ALL LLM calls go through this)
│   │   ├── embedding.py       # Single model enforcement (nomic-embed-text, 768d)
│   │   ├── chunking.py        # Contextual chunking (RecursiveCharacterTextSplitter)
│   │   ├── retrieval.py       # Hybrid BM25 + vector + RRF fusion
│   │   ├── knowledge.py       # Knowledge entry management
│   │   ├── feedback.py        # Feedback collection + aggregation
│   │   └── prompt_evolution.py # Tier 2: auto-update prompts from accumulated feedback
│   └── workers/
│       ├── tasks.py           # Celery task definitions
│       └── evaluation.py      # Scheduled: aggregate feedback, trigger Tier 2 loops
├── static/                    # CSS, JS (minimal), images
├── tests/
│   ├── test_pipeline/
│   ├── test_api/
│   ├── test_services/
│   ├── test_feedback_loops/
│   └── fixtures/
│       └── sample_transcript.txt
```

---

## 2. Model Routing Strategy

**All LLM calls go through `app/services/llm_client.py`.** Never call Ollama directly from pipeline nodes.

| Task | Model | Where | Rationale |
|------|-------|-------|-----------|
| Transcript Cleanup | qwen2.5:7b | Local Ollama | Light preprocessing — simple task |
| Topic Classification | qwen2.5:7b | Local Ollama | Constrained task, good with prompting |
| Classification Escalation | DeepSeek V3 / Kimi K2 | Ollama Cloud | Tier 1: low-confidence fallback |
| Transcript Segmentation | DeepSeek V3 / Kimi K2 | Ollama Cloud | Needs strong reasoning over long context |
| Report Generation | DeepSeek V3 / Kimi K2 | Ollama Cloud | Strong reasoning + writing quality |
| Executive Summary + Title | DeepSeek V3 / Kimi K2 | Ollama Cloud | Cross-domain synthesis |
| Education Transform | DeepSeek V3 / Kimi K2 | Ollama Cloud | Pedagogical restructuring |
| Chatbot (RAG Q&A) | qwen2.5:14b or cloud | Either | Start local, upgrade if quality insufficient |
| Embeddings (ALL) | nomic-embed-text | Local Ollama | 768d. SAME model for docs AND queries. NEVER mix. |

**Routing config:**
```python
TASK_ROUTING = {
    "preprocess": "local",
    "classify": "local",
    "classify_escalation": "cloud",
    "segment": "cloud",
    "report": "cloud",
    "synthesize": "cloud",
    "title": "cloud",
    "educate": "cloud",
    "chat": "local",
    "embed": "local",  # ALWAYS local
}
```

---

## 3. Environment Variables

```env
# Local Ollama
OLLAMA_LOCAL_URL=http://ollama:11434
OLLAMA_MODEL_PREPROCESS=qwen2.5:7b
OLLAMA_MODEL_CLASSIFY=qwen2.5:7b
OLLAMA_MODEL_EMBED=nomic-embed-text

# Cloud Ollama
OLLAMA_CLOUD_URL=https://api.ollama.com
OLLAMA_CLOUD_API_KEY=your-key
OLLAMA_MODEL_SEGMENT=deepseek-v3
OLLAMA_MODEL_REPORT=deepseek-v3
OLLAMA_MODEL_SYNTHESIZE=deepseek-v3
OLLAMA_MODEL_TITLE=deepseek-v3
OLLAMA_MODEL_EDUCATE=deepseek-v3
OLLAMA_MODEL_CHAT=qwen2.5:14b

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/sentinel
DATABASE_URL_SYNC=postgresql://postgres:postgres@db:5432/sentinel

# Redis
REDIS_URL=redis://redis:6379/0

# LangFuse (optional)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=http://langfuse:3000
```

---

## 4. Database Schema

### Core Tables

**sources** — Ingested videos/content
```
id (uuid, PK)
source_type (enum: youtube, article, linkedin, manual)
url (text, nullable)
title (text) — GENERATED by pipeline, not from YouTube
original_title (text) — raw YouTube title
author (text, nullable)
published_at (timestamptz, nullable)
raw_content (text) — full transcript
metadata (jsonb)
processing_status (enum: pending, processing, completed, failed)
created_at, updated_at (timestamptz)
```

**content_sections** — Segmented + classified transcript sections
```
id (uuid, PK)
source_id (uuid, FK → sources)
section_index (int)
content (text)
start_timestamp, end_timestamp (text, nullable)
domain (enum: dev_tooling, ai_solutions, business_dev, not_relevant)
classification_confidence (float)
classification_reasoning (text)
created_at (timestamptz)
```

**reports** — Generated domain reports + executive summaries
```
id (uuid, PK)
source_id (uuid, FK → sources)
report_type (enum: domain_specific, executive_summary)
domain (enum, nullable)
title (text)
content (text) — markdown formatted
key_takeaways (jsonb)
action_items (jsonb)
relevance_score (float)
model_used (text) — REQUIRED for Tier 3 analysis
prompt_version (text) — REQUIRED for Tier 3 analysis
created_at (timestamptz)
```

**knowledge_entries** — Approved content for knowledge base
```
id (uuid, PK)
source_id (uuid, FK → sources)
report_id (uuid, FK → reports, nullable)
domain (enum)
title, original_content, educational_content (text)
approval_status (enum: pending_report, approved_for_education, pending_education_review, approved, rejected)
approved_by (text, nullable)
approved_at (timestamptz, nullable)
tags (text[], nullable)
created_at, updated_at (timestamptz)
```

**knowledge_chunks** — Embedded chunks for RAG retrieval
```
id (uuid, PK)
knowledge_entry_id (uuid, FK)
chunk_index (int)
chunk_text (text)
context_summary (text)
domain (enum)
source_title, section_title (text)
tags (text[], nullable)
embedding (vector(768)) — pgvector
search_text (tsvector) — generated column for BM25
created_at (timestamptz)
```

### Feedback & Evolution Tables

**feedback** — All user feedback (classifications, reports, chat, titles)
```
id (uuid, PK)
target_type (enum: classification, report, chat_response, retrieval, title)
target_id (uuid)
rating (int)
correction (jsonb, nullable)
notes (text, nullable)
created_at (timestamptz)
```

**prompt_versions** — Tracks prompt evolution over time
```
id (uuid, PK)
prompt_name (text) — e.g. "classify", "report_dev"
version_hash (text) — SHA256 of content
content (text) — full prompt template
few_shot_examples (jsonb, nullable)
is_active (boolean)
activated_at (timestamptz)
performance_metrics (jsonb, nullable)
created_at (timestamptz)
```

**few_shot_bank** — Human-corrected examples for prompt injection
```
id (uuid, PK)
task_type (text)
input_text (text)
original_output (jsonb)
corrected_output (jsonb)
source_feedback_id (uuid, FK → feedback)
is_active (boolean)
created_at (timestamptz)
```

### Supporting Tables

**chat_sessions** / **chat_messages** — Chatbot conversations
**processing_jobs** — Pipeline job tracking (status, errors, metadata with trace_id)

---

## 5. Docker Compose

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes: ["./app:/app/app"]
    depends_on: [db, redis, ollama]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build: .
    env_file: .env
    depends_on: [db, redis, ollama]
    command: celery -A app.workers.tasks worker --loglevel=info

  scheduler:
    build: .
    env_file: .env
    depends_on: [db, redis]
    command: celery -A app.workers.tasks beat --loglevel=info

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: sentinel
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: [ollama_data:/root/.ollama]
    # Uncomment for GPU:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]

volumes:
  pgdata:
  ollama_data:
```

---

## 6. LangGraph Pipeline Flow

```
START
  │
  ▼
[extract_transcript] ── YouTube URL → raw transcript
  │
  ▼
[preprocess_transcript] ── Caption cleanup (local 7B)
  │
  ▼
[segment_transcript] ── Split into topical sections (cloud)
  │
  ▼
[classify_sections] ── Domain classification (local 7B, parallel)
  │                    Tier 1: auto-escalate low confidence to cloud
  │
  ├── "dev_tooling" ──► [generate_dev_report] (cloud)
  ├── "ai_solutions" ──► [generate_ai_report] (cloud)
  ├── "business_dev" ──► [generate_biz_report] (cloud)
  └── "not_relevant" ──► [skip]
  │
  ▼
[synthesize_executive_summary + generate_title] (cloud, single call)
  │
  ▼
[persist_results] ── Save to DB, update source title, record trace_id + prompt_versions
  │
  ▼
END
```

---

## 7. API Endpoints

### Sources & Processing
```
POST   /api/sources/youtube          — Submit URL(s) for processing
GET    /api/sources                  — List all sources
GET    /api/sources/{id}             — Get source details
POST   /api/sources/{id}/reprocess   — Re-run pipeline
DELETE /api/sources/{id}
PATCH  /api/sources/{id}/title       — Inline title edit (triggers Tier 2)
```

### Reports
```
GET    /api/reports
GET    /api/reports/{id}
```

### Knowledge Base (Phase 2+)
```
POST   /api/knowledge/approve
POST   /api/knowledge/reject
GET    /api/knowledge/pending
POST   /api/knowledge/{id}/transform
POST   /api/knowledge/{id}/publish
GET    /api/knowledge
GET    /api/knowledge/search
```

### Chat (Phase 3)
```
POST   /api/chat
GET    /api/chat/sessions
GET    /api/chat/sessions/{id}
```

### Feedback & Evaluation
```
POST   /api/feedback                  — Universal feedback endpoint
GET    /api/feedback/stats
GET    /api/feedback/classification-accuracy
GET    /api/feedback/report-quality
GET    /api/feedback/prompt-versions
POST   /api/feedback/prompt-rollback
```

### HTMX Pages
```
GET    /                             — Dashboard
GET    /videos/{id}                  — Video detail
GET    /domain/{domain}              — Domain filter view
GET    /knowledge                    — Knowledge base
GET    /chat                         — Chatbot
GET    /quality                      — Quality dashboard
GET    /settings
```

---

## 8. Frontend Stack

```html
<!-- base.html CDN imports -->
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
```

**Rules:**
- HTMX for all interactions (no JavaScript frameworks)
- API routes return JSON, page routes return HTML
- HTMX fragment routes return partial HTML for swap targets
- `hx-boost="true"` on body for SPA-like navigation
- Chat streaming via SSE: `hx-ext="sse"` + `sse-connect`
- One JS exception allowed: correction dropdown toggle after thumbs-down

---

## 9. Build Order (Phase 1)

This is the recommended implementation sequence:

1. Docker Compose + DB — all services running
2. Database models + Alembic migrations (include feedback/prompt_versions/few_shot_bank)
3. YouTube extraction service
4. LLM client abstraction (local + cloud routing)
5. Embedding service (verify 768d)
6. Prompt manager (versioning, few-shot injection)
7. Base HTMX layout + nav
8. "Add Video" form — paste URL, store, show on dashboard
9. Pipeline: extract + preprocess (local 7B)
10. Pipeline: segment (cloud model)
11. Pipeline: classify (local 7B + Tier 1 escalation)
12. Pipeline: domain reports (cloud, one at a time)
13. Pipeline: synthesize + title generation (cloud)
14. Background worker (Celery)
15. Feedback system (widgets, API, storage)
16. Prompt evolution service (Tier 2 wiring)
17. Basic quality dashboard (minimal stats)
18. Observability (LangFuse/LangSmith)
19. Polish UI (status, filters, loading, mobile)
