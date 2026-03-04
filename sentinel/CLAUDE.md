# CLAUDE.md — Sentinel Project

> Read this file FIRST on every session. It defines how you work, not what you build.
> For architecture details → `docs/ARCHITECTURE.md`
> For code patterns/examples → `docs/CODE_PATTERNS.md`
> For full requirements → `docs/REQUIREMENTS.md`

---

## 1. Session Startup Protocol

**Every time you start working (new session or after compaction), do this:**

1. Read `docs/PROGRESS.md` — understand what's been done and what's in flight
2. Read `tasks/todo.md` — see the current plan
3. If no plan exists or the current phase is complete, create one (see §2)
4. Briefly confirm with me: "Here's where we left off: [X]. I plan to work on [Y] next. Good?"
5. Only after my confirmation, begin working

**If context was compacted mid-session:** Re-read `docs/PROGRESS.md` before continuing. Do NOT guess what was done — read the file.

---

## 2. Planning Protocol

**Before writing ANY code, think → plan → verify → execute.**

### Creating a Plan
1. Read `docs/REQUIREMENTS.md` for the relevant phase
2. Read `docs/ARCHITECTURE.md` for tech decisions
3. Write a plan to `tasks/todo.md` using the template format
4. **STOP and check in with me** — I verify the plan before you start

### Todo Format
```markdown
## Current Phase: [Phase X — Name]
### Status: [Planning | In Progress | Review]

- [ ] Task 1 — brief description
- [ ] Task 2 — brief description
- [x] Task 3 — completed description

### Blocked
- (any blockers)

### Next Up
- (what comes after current tasks)
```

---

## 3. Execution Rules

### Simplicity First
- **One task at a time.** Finish it, test it, commit it, then move on.
- **Smallest possible changes.** Every change should touch as few files as possible.
- **No premature abstraction.** Build the simple thing first. Refactor later if needed.
- **If a task feels big, break it down** into 2-3 sub-tasks and list them in todo.md.

### After Completing Each Task
1. ✅ Mark the task complete in `tasks/todo.md`
2. 📝 Append a summary to `docs/PROGRESS.md` (see §5)
3. 🔀 Git commit with a descriptive message (see §4)
4. 💬 Tell me what you did in 1-2 sentences (high-level only)

### When Something Goes Wrong
- **Don't silently retry 5 times.** Tell me on the first failure.
- **Don't refactor surrounding code to fix a bug.** Fix the bug only.
- **If you're unsure between two approaches,** ask me. Don't guess.

---

## 3.5 Testing Requirements

**"Test it" is not optional.** Before every commit, the relevant tests must pass.

### Protocol
Use the `testing-gate` skill for ALL testing decisions. It defines:
- How to derive tests from code (business logic, edge cases, contracts, errors, regressions)
- The pre-commit gate sequence (identify → derive → write → run → verify → commit)
- Test quality rules and mocking strategy
- Language-specific patterns

### Project-Specific Context
All project-specific testing details live in `docs/TEST_CONTEXT.md`:
- Business requirements to test
- Technical constraints to enforce
- Test tiers and commands
- Task-to-test mapping
- Fixtures and test data
- Known gotchas

**If `docs/TEST_CONTEXT.md` doesn't exist, create one before writing tests.**

### Rules
- **Never commit with failing tests.**
- **A task is NOT done until its Tier A tests pass.**
- **Write tests AS PART of the task, not after.**
- Mark integration tests: `@pytest.mark.integration` — skipped by default locally.

---

## 4. Git Discipline

### Branching Strategy

- `main` — always stable. Only receives merges when a full group is complete and tested.
- `group/N-name` — one branch per group. All task commits go here.

**Branch naming:** `group/1-infrastructure`, `group/2-core-services`, `group/3-ui-shell`, `group/4-langgraph-pipeline`, etc.

**At the start of each group:**
```bash
git checkout main
git checkout -b group/N-name
git push -u origin group/N-name
```

**At the end of each group — STOP. Do NOT merge yourself.**
Tell the user the group is complete and ask them to approve the merge to `main`.

---

### Commit After Every Successful Change
```bash
git add -A
git commit -m "<type>: <short description>"
git push
```

> **Repo:** `https://github.com/joneal2022/ehKnowledgeBase.git`
> **Current branch:** always a `group/N-name` branch — never commit directly to `main`.
> Git user is configured globally on this machine. `git push` will always go to the correct private repo.

### Commit Types
- `feat:` — new feature or functionality
- `fix:` — bug fix
- `setup:` — project setup, config, infrastructure
- `refactor:` — code improvement without behavior change
- `docs:` — documentation only
- `test:` — adding or fixing tests

### Rules
- **Never commit broken code.** If tests exist, they must pass.
- **Never make giant commits.** One logical change per commit.
- **Always push after committing** so progress is saved.
- **Include the todo task number** when relevant: `feat: FR-1.1 youtube transcript extraction (#3)`

---

## 5. Progress Tracking

### Append to `docs/PROGRESS.md` after every completed task:

```markdown
### [Date] — [Task Name]
**What:** Brief description of what was built/changed
**Files:** List of key files created or modified
**Status:** Working / Partial / Needs Review
**Notes:** Any gotchas, decisions made, or things to revisit
```

### Rules
- **Be factual, not verbose.** Future-you (or a new session) needs to scan this fast.
- **Include file paths.** This is how the next session knows what exists.
- **Note any deviations from the plan.** If you did something differently, say why.
- **Record environment state.** "Docker services running," "DB migrated to version X," etc.

---

## 6. Project Identity

**Name:** Sentinel
**What it does:** Ingests YouTube transcripts → LangGraph multi-agent pipeline → domain-specific executive reports → searchable knowledge base → training chatbot
**Who it's for:** Solo business owner who can't watch 3-9 hours of Skool community videos per week
**Three domains:** (1) Dev Process & Tooling, (2) AI Solutions & Implementation, (3) Business Development & Growth
**Critical quirk:** YouTube titles are useless. System MUST generate descriptive titles from content.

---

## 7. Tech Stack (Non-Negotiable)

| Layer | Tech |
|-------|------|
| Backend | Python 3.12+ / FastAPI |
| Frontend | HTMX + Jinja2 + Tailwind CSS (NO React/Vue/SPA) |
| Agent Pipeline | LangGraph |
| LLM Local | Ollama (qwen2.5:7b for classify/preprocess, nomic-embed-text for embeddings) |
| LLM Cloud | Ollama Cloud / OpenRouter fallback (DeepSeek V3, Kimi K2) |
| Database | PostgreSQL + pgvector + tsvector (Docker locally, Supabase prod) |
| Queue | Celery + Redis |
| Observability | LangFuse (self-hosted) or LangSmith |
| Infrastructure | Docker Compose |

**See `docs/ARCHITECTURE.md` for full details, project structure, DB schema, and Docker config.**

---

## 8. Critical Don'ts

1. Don't hardcode model names — config/env only
2. Don't skip JSON parsing safety — `parse_llm_json()` always
3. Don't use JavaScript for UI — HTMX only (one exception: correction dropdown toggle)
4. Don't process videos synchronously — background worker only
5. Don't call Supabase during dev — local pgvector Docker
6. Don't mix embedding models — one model (`nomic-embed-text`), one service, everywhere
7. Don't use YouTube titles — generate titles from content
8. Don't build feedback as an afterthought — it's core, build in Phase 1
9. Don't write monolithic prompts — one file per prompt, `{few_shot_examples}` placeholder
10. Don't store reports without `model_used` + `prompt_version` — Tier 3 needs this

**See `docs/CODE_PATTERNS.md` for implementation examples of all critical patterns.**

---

## 9. File Reference Map

| Need to know... | Read this |
|------------------|-----------|
| What to build (features, phases, schemas) | `docs/REQUIREMENTS.md` |
| How to build it (structure, stack, Docker) | `docs/ARCHITECTURE.md` |
| Code examples & patterns | `docs/CODE_PATTERNS.md` |
| What's been done | `docs/PROGRESS.md` |
| What's being worked on now | `tasks/todo.md` |
| Environment variables | `.env.example` |
| Project-specific test context | `docs/TEST_CONTEXT.md` |

---

## 10. Communication Style

- **Tell me what you're about to do** before doing it (1 sentence)
- **Tell me what you did** after doing it (1-2 sentences)
- **Don't dump full file contents** in chat — just summarize changes
- **If you read a file, don't recite it back to me** — just use the information
- **Ask clarifying questions** rather than making assumptions
