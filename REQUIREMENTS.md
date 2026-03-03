# Requirements: AI-Powered Business Intelligence Platform

## Project Codename: **Sentinel**

> An AI-powered platform that ingests video transcripts (and eventually other sources), processes them through a LangGraph multi-agent pipeline, generates domain-specific executive reports, and builds a searchable knowledge base with a training chatbot.

---

## 1. Problem Statement

The user is part of a Skool community that hosts 3 live events per week (1–3 hours each). These videos contain high-value information across three strategic domains critical to the user's business. Watching 3–9 hours of video weekly is unsustainable. The platform must distill these videos into actionable intelligence automatically.

---

## 2. User Personas

### P1 — Business Owner (Primary User, Day 1)
- Reviews executive reports generated from video transcripts
- Approves/rejects content for the knowledge base
- Uses the dashboard to stay informed without watching videos
- Eventually queries the training chatbot for specific answers
- Provides feedback on pipeline quality (thumbs up/down on reports, classifications)

### P2 — Team Members (Future Users, Phase 3+)
- Access the training chatbot to learn about AI solutions, dev process improvements, and business strategy
- Cannot approve content — read-only access to approved knowledge base
- May eventually contribute their own knowledge sources

---

## 3. Strategic Topic Domains

All content processing revolves around three core business domains:

### Domain 1: Development Process & Tooling
- Keeping up with latest AI tooling releases (Claude Code, Cursor, etc.)
- Streamlining development workflows for a 15-dev team
- Best practices for AI-assisted development
- New frameworks, libraries, and development paradigms
- Code quality, testing, and deployment improvements

### Domain 2: AI Solutions & Implementation
- Setting up the company to handle AI solution clients
- AI architecture patterns and implementation strategies
- What AI solutions businesses are asking for
- Technical approaches to common AI problems
- Integration patterns, RAG, agents, automation
- How to scope, estimate, and deliver AI projects

### Domain 3: Business Development & Growth
- Systematic approaches to client acquisition (beyond referrals)
- ROI calculation methodologies for AI and custom software
- Case study creation and social proof strategies
- Hot verticals and market opportunities in AI
- Pricing strategies for AI solutions
- Sales processes and pipeline management
- Marketing and positioning for a custom software + AI company

---

## 4. System Architecture Overview

### 4.1 High-Level Flow

```
[YouTube URL / Playlist] 
        │
        ▼
[Transcript Extraction] ──► Raw transcript stored in DB
        │
        ▼
[LangGraph Pipeline] 
  ├── Preprocessing (Local 7B) ──► Clean up auto-caption artifacts
  ├── Segmentation Agent (Ollama Cloud) ──► Splits transcript into topical sections
  ├── Classification Agent (Local 7B) ──► Classifies each section into Domain 1/2/3 or "Not Relevant"
  ├── Domain-Specific Report Agents (Ollama Cloud) ──► Generate executive reports per domain
  ├── Synthesis Agent (Ollama Cloud) ──► Creates overall video executive summary
  └── Title Generation (Ollama Cloud) ──► Generates descriptive video title from content
        │
        ▼
[Dashboard / UI] ──► User reviews reports + provides feedback
        │                                    │
        │                    [Feedback Loop System]
        │                     ├── Tier 1: Automated (self-healing prompts, fallbacks)
        │                     ├── Tier 2: Semi-auto (corrections → prompt evolution)
        │                     └── Tier 3: Human (quality dashboard → strategic decisions)
        │
        ▼ (User approves)
[Education Transformation Agent] ──► Transforms content for learning
        │
        ▼ (User approves again)
[Contextual Chunking + Embedding] ──► Rich chunks with metadata
        │
        ▼
[Knowledge Base (pgvector + tsvector)] ──► Hybrid structured + vector storage
        │
        ▼
[Training Chatbot] ──► Hybrid retrieval (BM25 + semantic) RAG-powered Q&A
```

### 4.2 Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend** | HTMX + Jinja2 templates + Tailwind CSS | Server-rendered, minimal JS, sufficient for dashboards + approval workflows |
| **Backend** | Python 3.12+ / FastAPI | Async, great LangGraph/LLM ecosystem, Jinja2 integration |
| **Agent Orchestration** | LangGraph | Stateful multi-agent workflows, conditional routing, human-in-the-loop |
| **LLM Inference (Small/Local)** | Ollama local | Classification, simple tasks — $0 cost |
| **LLM Inference (Large/Cloud)** | Ollama Cloud (OpenRouter as fallback) | Segmentation, report generation, synthesis — uses DeepSeek, Kimi K2, etc. |
| **Database** | PostgreSQL + pgvector + tsvector (local dev via Docker, Supabase for prod) | Hybrid search: vector similarity + full-text BM25, structured queries, zero lock-in |
| **Embeddings** | Ollama local (nomic-embed-text, 768d) | Free, fast, good quality. Single model for all embeddings (docs + queries). |
| **Task Queue** | Celery + Redis (or ARQ) | Async video processing, background jobs |
| **Observability/Telemetry** | LangFuse (self-hosted, open source) OR LangSmith | Agent tracing, evaluation, feedback loops |
| **Local Dev** | Docker Compose | All services in one command |
| **Transcript Extraction** | youtube-transcript-api (Python) | No API key needed for public/unlisted videos with captions |

### 4.3 Model Strategy (Local Ollama + Ollama Cloud)

| Task | Model | Where | Rationale |
|------|-------|-------|-----------|
| **Topic Classification** | qwen2.5:7b | Local Ollama | Constrained task. 7B handles it well with good prompting. |
| **Transcript Cleanup** | qwen2.5:7b | Local Ollama | Light preprocessing — simple task. |
| **Transcript Segmentation** | DeepSeek V3 or Kimi K2 | Ollama Cloud | Needs strong reasoning over long context. 1 call per video. |
| **Executive Report Generation** | DeepSeek V3 or Kimi K2 | Ollama Cloud | Strong reasoning, synthesis, writing quality. |
| **Education Transformation** | DeepSeek V3 or Kimi K2 | Ollama Cloud | Pedagogical restructuring ability. |
| **Video Summary Synthesis** | DeepSeek V3 or Kimi K2 | Ollama Cloud | Cross-domain synthesis. |
| **Title Generation** | DeepSeek V3 or Kimi K2 | Ollama Cloud | Generates descriptive title from video content (original titles are useless). |
| **Chatbot (RAG Q&A)** | qwen2.5:14b (local) or DeepSeek (cloud) | Either | Start local, move to cloud if quality insufficient. |
| **Embeddings (ALL)** | nomic-embed-text | Local Ollama | 768d. CRITICAL: Same model for documents AND queries. Never mix. |

> **Note on video titles**: The Skool community videos have generic titles like "Live Recording 2025-01-15". The system MUST generate descriptive titles from the actual content. This happens during the synthesis step after all domain reports are complete, so the title reflects what the video actually covered.

### 4.4 Database Schema (PostgreSQL + pgvector + tsvector)

```
┌─────────────────────────────────────────┐
│ sources                                 │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ source_type (enum: youtube, article,    │
│              linkedin, manual)          │
│ url (text, nullable)                    │
│ title (text) -- GENERATED by pipeline,  │
│   not from YouTube metadata             │
│ original_title (text) -- raw YT title   │
│ author (text, nullable)                 │
│ published_at (timestamptz, nullable)    │
│ raw_content (text) -- full transcript   │
│ metadata (jsonb) -- flexible per type   │
│ processing_status (enum: pending,       │
│   processing, completed, failed)        │
│ created_at (timestamptz)                │
│ updated_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ content_sections                        │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ source_id (uuid, FK → sources)          │
│ section_index (int)                     │
│ content (text)                          │
│ start_timestamp (text, nullable)        │
│ end_timestamp (text, nullable)          │
│ domain (enum: dev_tooling,              │
│         ai_solutions, business_dev,     │
│         not_relevant)                   │
│ classification_confidence (float)       │
│ classification_reasoning (text)         │
│ created_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ reports                                 │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ source_id (uuid, FK → sources)          │
│ report_type (enum: domain_specific,     │
│              executive_summary)         │
│ domain (enum, nullable)                 │
│ title (text)                            │
│ content (text) -- markdown formatted    │
│ key_takeaways (jsonb) -- array          │
│ action_items (jsonb) -- array           │
│ relevance_score (float) -- 0-1          │
│ model_used (text) -- which model        │
│ prompt_version (text) -- prompt hash    │
│ created_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ knowledge_entries                       │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ source_id (uuid, FK → sources)          │
│ report_id (uuid, FK → reports, nullable)│
│ domain (enum)                           │
│ title (text)                            │
│ original_content (text)                 │
│ educational_content (text, nullable)    │
│ approval_status (enum: pending_report,  │
│   approved_for_education,               │
│   pending_education_review,             │
│   approved, rejected)                   │
│ approved_by (text, nullable)            │
│ approved_at (timestamptz, nullable)     │
│ tags (text[], nullable)                 │
│ created_at (timestamptz)                │
│ updated_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ knowledge_chunks                        │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ knowledge_entry_id (uuid, FK)           │
│ chunk_index (int)                       │
│ chunk_text (text)                       │
│ context_summary (text)                  │
│ domain (enum)                           │
│ source_title (text)                     │
│ section_title (text, nullable)          │
│ tags (text[], nullable)                 │
│ embedding (vector(768))                 │
│ search_text (tsvector)                  │ -- Generated column for BM25
│ created_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ chat_sessions                           │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ user_identifier (text)                  │
│ created_at (timestamptz)                │
│ updated_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ chat_messages                           │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ session_id (uuid, FK → chat_sessions)   │
│ role (enum: user, assistant)            │
│ content (text)                          │
│ sources_cited (jsonb, nullable)         │
│ retrieval_metadata (jsonb, nullable)    │
│ created_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ processing_jobs                         │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ source_id (uuid, FK → sources)          │
│ job_type (enum: full_pipeline,          │
│           reprocess, education_transform)│
│ status (enum: queued, running,          │
│         completed, failed)              │
│ started_at (timestamptz, nullable)      │
│ completed_at (timestamptz, nullable)    │
│ error_message (text, nullable)          │
│ metadata (jsonb) -- model, tokens,      │
│   latencies, trace_id, prompt_versions  │
│ created_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ feedback                                │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ target_type (enum: classification,      │
│   report, chat_response, retrieval,     │
│   title)                                │
│ target_id (uuid)                        │
│ rating (int) -- 1-5 or thumbs 1/0      │
│ correction (jsonb, nullable)            │ -- correct domain, better title, etc.
│ notes (text, nullable)                  │
│ created_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ prompt_versions                         │
│ (tracks prompt evolution over time)     │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ prompt_name (text) -- e.g. "classify",  │
│   "report_dev", "segment"              │
│ version_hash (text) -- SHA256 of content│
│ content (text) -- full prompt template  │
│ few_shot_examples (jsonb, nullable)     │ -- dynamically built from feedback
│ is_active (boolean, default true)       │
│ activated_at (timestamptz)              │
│ performance_metrics (jsonb, nullable)   │ -- avg rating, accuracy, etc.
│ created_at (timestamptz)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ few_shot_bank                           │
│ (human-corrected examples for prompts)  │
├─────────────────────────────────────────┤
│ id (uuid, PK)                           │
│ task_type (text) -- "classify",         │
│   "segment", "report", etc.            │
│ input_text (text) -- the original input │
│ original_output (jsonb) -- what the     │
│   model produced                        │
│ corrected_output (jsonb) -- what it     │
│   should have produced                  │
│ source_feedback_id (uuid, FK→feedback)  │
│ is_active (boolean, default true)       │ -- included in prompts when true
│ created_at (timestamptz)                │
└─────────────────────────────────────────┘
```

---

## 5. Knowledge Base Architecture (Detailed)

### 5.1 Why Hybrid Search (BM25 + Semantic Vector)

Pure vector similarity has known weaknesses:
- **Keyword blindness**: Searching "Claude Code" might miss chunks containing those exact words
- **Specificity**: BM25 excels at exact term matching, vectors excel at conceptual similarity
- **PostgreSQL supports both natively**: `tsvector`/`tsquery` + `pgvector`. No extra infrastructure.

### 5.2 Hybrid Retrieval Strategy

```
User Query
    │
    ├──► [BM25 Search] ── tsvector match → top 10 keyword matches
    ├──► [Vector Search] ── cosine similarity → top 10 semantic matches
    └──► [Reciprocal Rank Fusion] ── Combine, deduplicate, return top-k
```

### 5.3 Contextual Chunking Strategy

1. **Semantic splitting**: RecursiveCharacterTextSplitter (paragraph → sentence → word boundaries, 512 tokens, 64 overlap)
2. **Context enrichment**: Prepend metadata to each chunk before embedding
3. **Dual indexing**: vector embedding (IVFFlat/HNSW) + tsvector (GIN)
4. **Metadata preservation**: domain, source_title, section_title, tags denormalized on each chunk

---

## 6. Evaluation Framework & Feedback Loop System (DETAILED)

> This section describes how the system continuously improves itself. This is the core methodology for delivering high-quality AI systems to clients.

### 6.1 Philosophy: Three Tiers of Feedback Loops

The system has three tiers of feedback, from fully automated to human-driven. Each tier addresses different failure modes and operates on different timescales.

```
┌────────────────────────────────────────────────────────────────────┐
│                    FEEDBACK LOOP ARCHITECTURE                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  TIER 1: AUTOMATED (Self-Healing)                                 │
│  ─────────────────────────────────                                │
│  Trigger: System metrics cross thresholds                         │
│  Action: Automatic fallback, retry, or prompt switching           │
│  Timescale: Immediate (same pipeline run or next run)             │
│  Human involvement: None                                          │
│                                                                    │
│  TIER 2: SEMI-AUTOMATED (Human Signal → System Acts)              │
│  ─────────────────────────────────────────────────────            │
│  Trigger: User provides feedback via UI (thumbs, corrections)     │
│  Action: System accumulates feedback → auto-updates prompts       │
│  Timescale: Accumulates over 5-10 feedbacks, then triggers        │
│  Human involvement: Just clicking thumbs up/down + corrections    │
│                                                                    │
│  TIER 3: HUMAN ANALYSIS (Dashboard → Strategic Decisions)         │
│  ─────────────────────────────────────────────────────            │
│  Trigger: Weekly/monthly quality review                           │
│  Action: Model swaps, prompt rewrites, architecture changes       │
│  Timescale: Weekly/monthly review cycles                          │
│  Human involvement: Full analysis and decision-making             │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 6.2 Tier 1: Automated Self-Healing Loops

These are rules-based triggers that require zero human intervention. They handle common failure modes automatically.

#### Loop 1A: JSON Parse Failure Recovery
```
TRIGGER:  LLM returns unparseable JSON (classification, segmentation)
DETECT:   parse_llm_json() raises ValueError
ACTION:   
  1. Retry with same model + "strict" prompt variant that has more explicit 
     formatting instructions and a concrete example
  2. If retry fails → retry with next-tier model (e.g., 7B → 14B)
  3. If that fails → log error, mark section as "needs_review", continue pipeline
METRIC:   Track parse_failure_rate per model per task
ALERT:    If rate > 20% over last 10 runs → surface in quality dashboard
```

#### Loop 1B: Low-Confidence Classification Escalation
```
TRIGGER:  Classification confidence < 0.6
DETECT:   Parsed JSON has confidence field < threshold
ACTION:   
  1. Re-classify using the cloud model instead of local 7B
  2. If cloud model also < 0.6 → flag as "ambiguous" in UI for human review
  3. Store both classifications for comparison (helps identify domain boundary issues)
METRIC:   Track escalation_rate (% of sections needing escalation)
```

#### Loop 1C: Retrieval Fallback Chain (Phase 3 - Chatbot)
```
TRIGGER:  Hybrid search returns < 2 relevant results
DETECT:   RRF fusion produces fewer than min_results
ACTION:   
  1. If BM25 returned 0 hits → retry with vector-only (broader semantic match)
  2. If vector returned 0 hits → retry with BM25-only (keyword fallback)
  3. If both empty → expand search (remove domain filter, increase top_k)
  4. If still empty → respond with "I don't have information on that topic yet"
METRIC:   Track empty_retrieval_rate, fallback_trigger_rate
```

#### Loop 1D: Model Timeout/Failure Handling
```
TRIGGER:  Ollama Cloud request times out or returns error
DETECT:   HTTP timeout (120s for report, 30s for classification)
ACTION:   
  1. Retry once with same model
  2. If cloud is down → queue job for later, mark as "waiting_for_cloud"
  3. If local model fails → check if Ollama container is running, restart if needed
METRIC:   Track cloud_availability, local_availability, retry_success_rate
```

### 6.3 Tier 2: Semi-Automated Feedback Loops

These loops require minimal human effort (just clicking in the UI) but produce significant system improvements over time. **This is the most important tier for client projects.**

#### Loop 2A: Classification Prompt Evolution via Corrections
```
HOW IT WORKS:
  1. User sees a misclassified section (e.g., labeled "business_dev" but it's "ai_solutions")
  2. User clicks 👎 on the classification and selects the correct domain
  3. This creates a record in `feedback` (rating=0, correction={"correct_domain": "ai_solutions"})
  4. AND creates a record in `few_shot_bank`:
     - input_text: the section content
     - original_output: {"domain": "business_dev", "confidence": 0.7}
     - corrected_output: {"domain": "ai_solutions"}

AUTOMATIC PROMPT UPDATE (triggered when few_shot_bank has >= 5 active examples for "classify"):
  1. System selects the 3-5 most diverse correction examples from few_shot_bank
  2. Injects them as few-shot examples into the classification prompt:
     
     "Here are examples of correct classifications:
      
      Section: '{example_1_input}'
      Classification: {example_1_corrected_output}
      
      Section: '{example_2_input}'  
      Classification: {example_2_corrected_output}
      ..."
  
  3. New prompt version is saved to `prompt_versions` table
  4. Next pipeline run automatically uses the updated prompt
  5. Old prompt version is retained (can rollback)

WHAT THE USER DOES: Click 👎, select correct domain. That's it.
WHAT THE SYSTEM DOES: Accumulates corrections → rebuilds few-shot examples → updates prompt.
```

#### Loop 2B: Report Quality → Model Comparison Signal
```
HOW IT WORKS:
  1. User rates reports 1-5 stars
  2. Each report stores which model and prompt version produced it
  3. System tracks average rating per (model × prompt_version × domain)

AUTOMATIC ACTIONS:
  - When a model's avg rating drops below 3.0 for a domain over 5+ rated reports:
    → Surface a recommendation in quality dashboard: "DeepSeek V3 is underperforming 
       for Business Dev reports (avg 2.8/5). Consider switching to Kimi K2."
  - When enough data exists (10+ reports per model):
    → Auto-generate comparison chart on quality dashboard

WHAT THE USER DOES: Rate reports 1-5 stars.
WHAT THE SYSTEM DOES: Tracks quality by model, surfaces recommendations.
```

#### Loop 2C: RAG Retrieval Quality → Chunk Tuning Signal (Phase 3)
```
HOW IT WORKS:
  1. Every chat response shows its source citations
  2. User can flag: "This source was helpful ✓" or "This source was wrong ✗"
  3. System tracks per-chunk hit rate (times cited & marked helpful / times retrieved)

AUTOMATIC ACTIONS:
  - Chunks with < 20% helpfulness rate over 10+ retrievals:
    → Flag for review: "This chunk is frequently retrieved but rarely helpful"
    → Possible causes: chunk is too vague, too large, missing context
  - If many chunks from a single knowledge_entry have low hit rates:
    → Suggest re-chunking that entry with different parameters
  - Track which domain filters improve results:
    → If domain-filtered queries have 2x higher satisfaction than unfiltered:
    → Default to asking "which domain?" before searching

WHAT THE USER DOES: Click ✓/✗ on source citations.
WHAT THE SYSTEM DOES: Identifies bad chunks, surfaces re-chunking suggestions.
```

#### Loop 2D: Title Quality Feedback
```
HOW IT WORKS:
  1. Generated titles shown on dashboard
  2. User can edit a title inline (the edit is saved as feedback with correction)
  3. Edited titles become few-shot examples for the title generation prompt

WHAT THE USER DOES: Occasionally edit a bad title.
WHAT THE SYSTEM DOES: Learns what good titles look like from corrections.
```

### 6.4 Tier 3: Human Analysis & Strategic Decisions

This tier uses the Quality Dashboard to surface insights that require human judgment.

#### Quality Dashboard Components

**Component 1: Pipeline Health Panel**
```
┌──────────────────────────────────────────────┐
│  PIPELINE HEALTH (Last 30 days)              │
├──────────────────────────────────────────────┤
│  Videos Processed:     12/12 ✅               │
│  Avg Processing Time:  7m 23s                │
│  Parse Failure Rate:   3% (▼ from 8%)        │
│  Cloud Availability:   99.2%                 │
│  Escalation Rate:      12% of classifications│
└──────────────────────────────────────────────┘
```
**Decisions this informs:**
- If processing time is climbing → check if model got slower, or transcripts are longer
- If parse failure rate is high → prompts need tightening, or model is unreliable
- If escalation rate is high → classification prompt needs better domain definitions

**Component 2: Classification Accuracy Panel**
```
┌──────────────────────────────────────────────┐
│  CLASSIFICATION ACCURACY (by domain)         │
├──────────────────────────────────────────────┤
│  Dev/Tooling:    92% ✅ (36 rated, 33 correct)│
│  AI Solutions:   88% ✅ (41 rated, 36 correct)│
│  Business Dev:   71% ⚠️ (28 rated, 20 correct)│
│  Not Relevant:   95% ✅ (15 rated, 14 correct)│
│                                               │
│  Common Misclassifications:                   │
│  "AI pricing strategy" → biz_dev (should be  │
│   ai_solutions? or both?)                     │
│  "Building AI sales team" → ai_solutions     │
│   (should be biz_dev)                         │
└──────────────────────────────────────────────┘
```
**Decisions this informs:**
- Business Dev at 71% → the domain definition is ambiguous for topics that overlap AI + business
- Action: Refine domain definitions in the classification prompt, add boundary examples
- Action: Consider adding a "multi-domain" classification option for content that spans domains

**Component 3: Report Quality by Model**
```
┌──────────────────────────────────────────────┐
│  REPORT QUALITY (avg rating by model)        │
├──────────────────────────────────────────────┤
│                 DeepSeek V3    Kimi K2        │
│  Dev/Tooling:   4.2 ⭐ (n=8)  3.9 ⭐ (n=5)  │
│  AI Solutions:  4.5 ⭐ (n=12) 4.3 ⭐ (n=7)  │
│  Business Dev:  3.1 ⭐ (n=6)  4.0 ⭐ (n=8)  │
│  Exec Summary:  4.0 ⭐ (n=10) 3.8 ⭐ (n=6)  │
│                                               │
│  💡 Recommendation: Switch Business Dev       │
│     reports to Kimi K2 (3.1 → 4.0 expected) │
└──────────────────────────────────────────────┘
```
**Decisions this informs:**
- Different models may be better for different domains
- Action: Route Business Dev reports to Kimi K2, keep DeepSeek for AI Solutions
- This is a config change, not a code change

**Component 4: Retrieval Quality (Phase 3)**
```
┌──────────────────────────────────────────────┐
│  RAG PERFORMANCE (Last 30 days)              │
├──────────────────────────────────────────────┤
│  Chat Responses:     45                      │
│  "Helpful" Rate:     78%                     │
│  "Wrong Sources":    8 flagged               │
│  Avg Sources/Query:  4.2                     │
│  Empty Retrieval:    3 (7%)                  │
│                                               │
│  Problem Chunks (frequently retrieved,        │
│  rarely helpful):                             │
│  - chunk_id_abc: "Overview of AI trends..."  │
│    Retrieved 12x, helpful 1x. TOO VAGUE.     │
│  - chunk_id_def: "Various pricing models..." │
│    Retrieved 8x, helpful 2x. TOO BROAD.     │
└──────────────────────────────────────────────┘
```
**Decisions this informs:**
- Vague chunks are polluting retrieval → re-chunk those knowledge entries with smaller sizes
- 78% helpful rate is decent but improvable → review the system prompt for the chatbot
- Empty retrieval at 7% → acceptable, but check what topics are missing from KB

**Component 5: Prompt Version Performance**
```
┌──────────────────────────────────────────────┐
│  PROMPT VERSIONS                             │
├──────────────────────────────────────────────┤
│  classify_v1 (Jan 1-15):  82% accuracy       │
│  classify_v2 (Jan 15+):   89% accuracy  ▲   │
│  (v2 added 3 few-shot examples from feedback)│
│                                               │
│  report_biz_v1 (Jan 1-20): 3.1 avg rating   │
│  report_biz_v2 (Jan 20+):  3.8 avg rating ▲ │
│  (v2 added more specific action items prompt)│
│                                               │
│  [Rollback to v1] [Export prompt history]     │
└──────────────────────────────────────────────┘
```
**Decisions this informs:**
- Prompt changes are tracked with their impact on quality
- If a new prompt version performs worse → one-click rollback
- Over time, builds a clear picture of what prompt changes actually improve results

### 6.5 How This Applies to Client Projects

This three-tier framework is reusable for any AI system you build for clients:

**For every AI pipeline node in a client project, ask:**

1. **What can fail silently?** → Build Tier 1 automated recovery
   - LLM output parsing failures → retry with strict prompt
   - Low confidence → escalate to better model
   - Service unavailable → queue and retry

2. **What needs human signal to improve?** → Build Tier 2 feedback UI
   - Classification accuracy → corrections that update few-shot examples
   - Output quality → ratings that compare models
   - Retrieval quality → source flagging that identifies bad chunks

3. **What requires strategic judgment?** → Build Tier 3 dashboard
   - Model selection across tasks
   - Domain definition refinement
   - Architecture decisions (chunk size, retrieval strategy)
   - ROI of the system (time saved vs. cost)

**The key insight: Tier 2 is where most of the value is.** It turns normal usage into system improvement with zero extra effort from the user beyond clicking thumbs up/down. This is what separates a good AI system from a great one, and it's the methodology that produces measurable improvement over time for clients.

### 6.6 Evaluation Data Flow Diagram

```
USER ACTION                    SYSTEM RESPONSE              IMPROVEMENT
─────────────                  ───────────────              ───────────
👎 classification              → Store in feedback           → Add to few_shot_bank
  + select correct domain      → Create few_shot_bank entry  → When bank >= 5 examples:
                                                               Auto-rebuild prompt
                                                               Save new prompt_version
                                                               Next run uses new prompt

⭐⭐⭐ rate report              → Store in feedback           → Track avg by model×domain
                               → Link to model_used,          → Surface recommendations
                                 prompt_version                  in quality dashboard

✗ flag wrong source (chat)     → Store in feedback           → Track chunk hit rate
                               → Log retrieval_metadata       → Flag bad chunks
                                                             → Suggest re-chunking

✏️ edit generated title        → Store as feedback           → Add to title few_shot_bank
                                 with correction             → Improve title generation

[No user action needed]        → Track parse failures         → Auto-retry with strict prompt
                               → Track latency                → Auto-escalate on failure
                               → Track availability           → Auto-queue on cloud downtime
```

---

## 7. Functional Requirements

### Phase 1 — Core Pipeline (MVP)

#### FR-1.1: YouTube Transcript Ingestion
- User can paste one or more YouTube URLs into the UI
- System extracts transcript using `youtube-transcript-api`
- If auto-captions unavailable, system reports error gracefully
- **Original YouTube title stored as `original_title`** (these are generic like "Live Recording {date}")
- Processing status displayed in UI (queued → processing → completed/failed)
- Support for bulk URL paste (one per line)

#### FR-1.2: Transcript Preprocessing
- Light cleanup of auto-caption artifacts (run-on text, missing punctuation)
- Use local 7B model to add sentence boundaries where needed

#### FR-1.3: Transcript Segmentation
- Uses Ollama Cloud model — needs strong reasoning over long context
- Each section represents a single topic/discussion point
- Preserves approximate timestamps
- Target: 3-15 sections per hour of content

#### FR-1.4: Topic Classification
- Uses local 7B model (qwen2.5:7b)
- Includes confidence score (0-1) and reasoning
- **Tier 1 loop**: confidence < 0.6 → auto-escalate to cloud model
- **Tier 2 loop**: user corrections → accumulate in few_shot_bank → auto-update prompt

#### FR-1.5: Domain-Specific Report Generation
- Uses Ollama Cloud model
- Reports include: Title, Summary, Key Takeaways, Action Items, Relevance Assessment, Business Application
- **Each report stores `model_used` and `prompt_version`** for Tier 3 analysis
- User can rate reports 1-5 stars

#### FR-1.6: Executive Summary + Title Generation
- Synthesis agent creates overall video summary
- **Title Generation**: Based on all domain reports, generates a descriptive title that replaces the generic YouTube title
  - Title prompt: "Based on these insights from the video, generate a concise, descriptive title (max 80 chars) that captures the main topics covered. Do NOT use the original title: '{original_title}'"
  - Title stored as `sources.title`, original kept as `sources.original_title`
  - User can inline-edit the title → creates feedback for Tier 2 loop

#### FR-1.7: Dashboard UI
- Home/Feed View showing generated titles (not YouTube titles), domain tags, TL;DR
- Video Detail View with all reports
- Domain Filter View
- **Feedback widgets**: 👍/👎 on classifications, ⭐ rating on reports, inline title editing

#### FR-1.8: Observability + Feedback Infrastructure
- LangFuse/LangSmith integrated from day 1
- Every pipeline run traced
- `feedback` table + `few_shot_bank` table + `prompt_versions` table created
- Basic quality dashboard page (can be minimal in Phase 1)
- Tier 1 automated loops wired into pipeline nodes

### Phase 2 — Knowledge Base & Approval Workflow

#### FR-2.1: Content Approval Workflow
- Approve/reject buttons on reports
- Bulk approve/reject capability

#### FR-2.2: Education Transformation Agent
- Transforms approved content into educational format
- Self-contained, includes "Why This Matters" and "How To Apply This"
- Final approval before persistence

#### FR-2.3: Contextual Chunking & Embedding
- Semantic/recursive text splitter
- Context metadata prepended before embedding
- nomic-embed-text (768d) — SAME model for all
- Both vector + tsvector indexes

### Phase 3 — Training Chatbot

#### FR-3.1: Hybrid Retrieval RAG Chat
- BM25 + vector + RRF fusion
- Domain pre-filtering option
- Source citations with links
- Streaming via SSE
- **Tier 1 loop**: retrieval fallback chain
- **Tier 2 loop**: source flagging → chunk quality tracking

#### FR-3.2: Chat Feedback
- "Was this helpful?" per response
- "Wrong source" flag per citation
- Retrieval metadata stored for debugging

### Phase 4 — Multi-Source Expansion

- Article, LinkedIn, manual ingestion
- Same downstream pipeline

### Phase 5 — Full Quality Dashboard & Optimization

#### FR-5.1: Quality Dashboard (complete version)
- Pipeline health panel
- Classification accuracy by domain (with common misclassification patterns)
- Report quality by model × domain (with switch recommendations)
- Retrieval quality metrics + problem chunk identification
- Prompt version comparison with performance tracking
- One-click prompt rollback

#### FR-5.2: Model A/B Testing Interface
- Select a task → select two models → run same input through both
- Blind rating (user doesn't know which model produced which)
- Win rate tracking

#### FR-5.3: Prompt Management UI
- View active prompt per task
- See few-shot examples (auto-generated from feedback)
- Manually add/remove few-shot examples
- View prompt version history with performance delta
- Export/import prompts

---

## 8. Non-Functional Requirements

### NFR-1: Performance
- Transcript extraction: < 30 seconds
- Full pipeline: < 10 minutes per 1-hour video
- Dashboard page load: < 2 seconds
- Chat response: < 15 seconds
- Hybrid retrieval: < 500ms

### NFR-2: Cost
- Local LLM: $0/month
- Ollama Cloud: < $5/month
- Database: $0/month
- Telemetry: $0/month (LangFuse self-hosted or LangSmith free tier)
- **Total target: < $10/month**

### NFR-3: Reliability
- Retryable jobs from UI
- Idempotent pipeline
- Tier 1 automated recovery for all common failures
- Graceful degradation when cloud/local unavailable

### NFR-4: Extensibility
- New source type: extractor + enum only
- New domain: enum + prompt only
- Model swap: config change only
- New evaluation metric: add to feedback target_type enum + dashboard component

### NFR-5: Hardware
- Local 7B: 16GB RAM minimum
- Local 14B: 32GB+ RAM or 12GB+ VRAM
- If limited: route everything to cloud (~$10-15/month)

---

## 9. LangGraph Pipeline

```
START
  │
  ▼
[extract_transcript] ── YouTube URL → transcript
  │
  ▼
[preprocess_transcript] ── Caption cleanup (local 7B)
  │
  ▼
[segment_transcript] ── Topical sections (cloud model)
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
[synthesize_executive_summary + generate_title] (cloud)
  │
  ▼
[persist_results] ── Save to DB, update source title, record trace_id + prompt_versions
  │
  ▼
END
```

---

## 10. API Endpoints

### Sources & Processing
```
POST   /api/sources/youtube
GET    /api/sources
GET    /api/sources/{id}
POST   /api/sources/{id}/reprocess
DELETE /api/sources/{id}
PATCH  /api/sources/{id}/title        — Inline title edit (triggers Tier 2 feedback)
```

### Reports
```
GET    /api/reports
GET    /api/reports/{id}
```

### Knowledge Base
```
POST   /api/knowledge/approve
POST   /api/knowledge/reject
GET    /api/knowledge/pending
POST   /api/knowledge/{id}/transform
POST   /api/knowledge/{id}/publish
GET    /api/knowledge
GET    /api/knowledge/search
```

### Chat
```
POST   /api/chat
GET    /api/chat/sessions
GET    /api/chat/sessions/{id}
DELETE /api/chat/sessions/{id}
```

### Feedback & Evaluation
```
POST   /api/feedback                   — Submit any feedback
GET    /api/feedback/stats             — Quality metrics
GET    /api/feedback/classification-accuracy
GET    /api/feedback/report-quality
GET    /api/feedback/retrieval-quality
GET    /api/feedback/prompt-versions   — Prompt history + performance
POST   /api/feedback/prompt-rollback   — Rollback to previous version
```

### HTMX Pages
```
GET    /
GET    /videos/{id}
GET    /domain/{domain}
GET    /knowledge
GET    /chat
GET    /quality                        — Quality/evaluation dashboard
GET    /settings
```

---

## 11. Phased Delivery

| Phase | Scope |
|-------|-------|
| **Phase 1** | YouTube ingestion → pipeline → dashboard + feedback infrastructure + Tier 1 loops |
| **Phase 2** | Approval workflow → education transform → contextual chunking → KB |
| **Phase 3** | Hybrid RAG chatbot + retrieval feedback loops |
| **Phase 4** | Multi-source ingestion |
| **Phase 5** | Full quality dashboard, A/B testing, prompt management UI, auth |

---

## 12. Open Questions

1. Verify Ollama Cloud model availability (DeepSeek V3, Kimi K2). OpenRouter as fallback.
2. Verify nomic-embed-text dimension from Ollama (expected 768).
3. pgvector index: start IVFFlat, switch HNSW if needed.
4. LangFuse vs LangSmith: try LangFuse first (self-hosted, free).
5. Benchmark qwen2.5:7b locally — if too slow, route classification to cloud.
6. Title generation: single call at end of pipeline vs. separate step? (Recommend: part of synthesis call to save a cloud API call.)
