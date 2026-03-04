# TEST_CONTEXT.md — Sentinel

> Project-specific testing context. The `testing-gate` skill reads this file.

---

## 1. Project Purpose

**Project:** Sentinel
**Purpose:** Ingests YouTube transcripts → LangGraph multi-agent pipeline → domain-specific executive reports → searchable knowledge base → training chatbot. Turns 3-9 hours of weekly Skool community videos into scannable, searchable knowledge.
**Users:** Solo business owner who can't watch hours of video. They need accurate, well-organized reports with content-derived titles (not YouTube's useless titles).

---

## 2. Business Requirements to Test

| ID | Business Requirement | Test Should Verify |
|----|---------------------|--------------------|
| BR-1 | Reports must use content-derived titles, never YouTube titles | Output title ≠ input `original_title`; title reflects transcript content |
| BR-2 | All reports must include `model_used` and `prompt_version` metadata | Report object has non-null `model_used` and `prompt_version` fields |
| BR-3 | Transcripts must be classified into one of three domains | `classify()` returns one of: Dev Process, AI Solutions, Business Development |
| BR-4 | Reports must be searchable via both semantic (vector) and keyword (tsvector) search | Search returns relevant results for both query types |
| BR-5 | Feedback is core — users can flag and correct report sections | Feedback endpoint accepts corrections and stores them with report linkage |
| BR-6 | Video processing must be asynchronous (background worker) | Ingest endpoint returns immediately; processing happens via Celery task |

---

## 3. Technical Constraints to Test

| ID | Technical Constraint | Test Should Verify |
|----|---------------------|--------------------|
| TC-1 | Model names from config only, never hardcoded | `get_model_for_task()` returns correct model per task; no model string literals in service code |
| TC-2 | All LLM JSON responses parsed through `parse_llm_json()` | Service functions use `parse_llm_json()`, not raw `json.loads()` on LLM output |
| TC-3 | Single embedding model (`nomic-embed-text`) everywhere | `EmbeddingService` uses config model; no other embedding model referenced |
| TC-4 | HTMX only for frontend — no JavaScript frameworks | No React/Vue/Angular imports in templates; HTMX attributes present |
| TC-5 | One prompt file per prompt with `{few_shot_examples}` placeholder | Prompt files exist per task; each contains the placeholder string |
| TC-6 | Local pgvector Docker in dev, never Supabase | DB connection string in test config points to localhost, not supabase.co |

---

## 4. Domain Rules

| ID | Domain Rule | Example Test Case |
|----|------------|-------------------|
| DR-1 | Transcripts < 200 words → classified as "insufficient" | 150-word input → `classify()` returns `ContentStatus.INSUFFICIENT` |
| DR-2 | Embedding search uses cosine similarity (pgvector `<=>`) | `search_similar()` SQL contains `<=>` operator |
| DR-3 | Reports without `model_used` metadata cannot be used for Tier 3 prompt evolution | `validate_report_for_evolution()` rejects reports missing `model_used` |
| DR-4 | YouTube titles stored as `original_title` but never surfaced to user | Report API response contains `generated_title`, not `original_title` |

---

## 5. Test Tiers

### Tier A — Unit Tests
- **When to run:** Before every commit
- **Command:** `uv run pytest tests/ -v`
- **External deps required:** None
- **What they cover:** Config routing, model definitions, enum values, service logic with mocks, pipeline node state transitions with mocks

### Tier B — Integration Tests
- **When to run:** Before merging group branch to main
- **Command:** `uv run pytest tests/ -v -m integration`
- **External deps required:** Docker (PostgreSQL + pgvector, Redis, Ollama)
- **What they cover:** Real DB CRUD, cascade deletes, vector/tsvector columns, real Ollama LLM calls, real pipeline runs on sample transcript, Alembic migrations

---

## 6. Test Structure

```
tests/
├── conftest.py                   # shared fixtures (settings, async session, mock LLM)
├── test_services/
│   ├── test_config.py            # config unit tests
│   ├── test_llm_client.py        # LLM client with mocked responses
│   ├── test_embedding_service.py # embedding service with mocked model
│   └── test_prompt_manager.py    # prompt loading and rendering
├── test_models/
│   └── test_models.py            # model definitions, enums, columns
├── test_pipeline/
│   ├── test_classify.py          # classification node with mocks
│   └── test_prompt_evolution.py  # Tier 2 evolution logic
├── test_api/
│   └── test_feedback.py          # feedback endpoints
└── fixtures/
    └── sample_transcript.txt     # ~500 word fake transcript for pipeline tests
```

---

## 7. Task-to-Test Mapping

| Task Type | Unit Tests (Tier A) | Integration Tests (Tier B) |
|-----------|--------------------|-----------------------------|
| Config / env | `get_model_for_task()` defaults, env var overrides | — |
| DB models | Enum values, column names, nullability, FK defs | CRUD, CASCADE delete, tsvector/vector columns |
| Services | Mock LLM/DB — test routing logic, output parsing | Real Ollama/DB calls |
| Pipeline nodes | Mock all services — test state transitions | Real pipeline run on sample transcript |
| API endpoints | `TestClient` with mock DB | Real DB + full request cycle |
| Migrations | `alembic heads` parses cleanly | `alembic upgrade head` + psql table list |
| Prompts | Template renders with placeholders filled | LLM returns parseable response from rendered prompt |

---

## 8. Fixtures & Test Data

| Fixture | Location | Contains | Used By |
|---------|----------|----------|---------|
| sample_transcript | `tests/fixtures/sample_transcript.txt` | ~500 word fake transcript covering AI tooling topic | Pipeline tests, classification tests |
| mock_llm_classify_response | `tests/conftest.py` | Realistic JSON: `{"domain": "ai_solutions", "confidence": 0.87, "reasoning": "..."}` | Classification service tests |
| mock_llm_report_response | `tests/conftest.py` | Realistic report JSON with generated_title, sections, model_used | Report generation tests |
| mock_embedding_vector | `tests/conftest.py` | 768-dim float array matching nomic-embed-text output shape | Embedding service tests |

---

## 9. Known Gotchas

- Ollama sometimes returns JSON wrapped in markdown code fences (```json ... ```) — mock responses must include this to test `parse_llm_json()` resilience
- pgvector requires `CREATE EXTENSION vector` — integration test DB setup must include this
- Celery tasks are async — unit tests should mock `.delay()` call; integration tests should use `CELERY_ALWAYS_EAGER=True`
- nomic-embed-text returns 768-dim vectors — mock vectors must match this dimensionality or pgvector operations will fail
- Alembic `heads` can silently diverge if multiple migrations are created in parallel — test for single head

---

## 10. Coverage Gaps (Living Section)

| Area | Gap | Priority | Status |
|------|-----|----------|--------|
| LLM response parsing | No test for completely unparseable LLM output (not even markdown-wrapped) | High | Open |
| Concurrent video processing | No test for two videos being processed simultaneously | Medium | Open |
| Feedback loop | No test verifying feedback actually influences prompt evolution | High | Open |
| Search ranking | No test for relevance ordering of search results | Medium | Open |
