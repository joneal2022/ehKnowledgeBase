# CODE_PATTERNS.md — Sentinel Implementation Patterns

> This file contains code examples and patterns for key Sentinel components.
> Read this when implementing specific features. Don't read all of it upfront — use it as a reference.

---

## 1. LLM Client — Local vs. Cloud Routing

**ALL LLM calls go through a single client.** Never call Ollama directly from nodes.

```python
# app/services/llm_client.py
from enum import Enum

class InferenceTarget(Enum):
    LOCAL = "local"
    CLOUD = "cloud"

TASK_ROUTING = {
    "preprocess": InferenceTarget.LOCAL,
    "classify": InferenceTarget.LOCAL,
    "classify_escalation": InferenceTarget.CLOUD,
    "segment": InferenceTarget.CLOUD,
    "report": InferenceTarget.CLOUD,
    "synthesize": InferenceTarget.CLOUD,
    "title": InferenceTarget.CLOUD,
    "educate": InferenceTarget.CLOUD,
    "chat": InferenceTarget.LOCAL,
    "embed": InferenceTarget.LOCAL,  # ALWAYS local
}

class LLMClient:
    async def generate(self, prompt: str, task: str, **kwargs) -> str:
        target = TASK_ROUTING.get(task, InferenceTarget.CLOUD)
        model = settings.get_model_for_task(task)
        
        if target == InferenceTarget.LOCAL:
            return await self._call_local(model, prompt, **kwargs)
        else:
            return await self._call_cloud(model, prompt, **kwargs)
    
    async def embed(self, text: str) -> list[float]:
        """ALWAYS local, ALWAYS same model."""
        return await self._call_local_embed(settings.OLLAMA_MODEL_EMBED, text)
```

---

## 2. Title Generation (Part of Synthesis Step)

Title generation happens in the synthesis node to save an API call.

```python
# app/pipeline/nodes/synthesize.py

SYNTHESIZE_AND_TITLE_PROMPT = """
You are analyzing a video that was part of a Skool community live event.
The original title is generic and unhelpful: "{original_title}"

Based on all the insights extracted below, perform two tasks:

TASK 1 - EXECUTIVE SUMMARY:
Create a concise executive summary with:
- TL;DR (3 sentences max)
- Don't Miss (the single most important insight)
- Domain breakdown (which domains were covered and what stood out)

TASK 2 - GENERATE TITLE:
Create a descriptive, specific title (max 80 characters) that captures the 
main topics covered. Make it informative enough that someone scanning a list 
would know exactly what value this video provides.

Bad titles: "Live Recording Jan 15", "Weekly Update", "Community Call"
Good titles: "RAG Architecture Deep-Dive + AI Consulting Pricing Strategies"

DOMAIN REPORTS:
{domain_reports_text}

Respond with ONLY JSON:
{{
  "title": "<generated title, max 80 chars>",
  "tldr": "<3 sentences max>",
  "dont_miss": "<single most important insight>",
  "domain_breakdown": {{
    "dev_tooling": "<1 sentence or null if not covered>",
    "ai_solutions": "<1 sentence or null>",
    "business_dev": "<1 sentence or null>"
  }}
}}
"""
```

**Title stored as `sources.title`**, original YouTube title kept as `sources.original_title`.

### Inline Title Editing (HTMX)

```html
<!-- components/inline_title_edit.html -->
<h2 id="title-{{ source.id }}" 
    hx-get="/api/sources/{{ source.id }}/title-edit"
    hx-trigger="dblclick"
    hx-swap="outerHTML"
    class="text-xl font-bold cursor-pointer hover:bg-gray-50 rounded px-1"
    title="Double-click to edit">
  {{ source.title }}
</h2>

<!-- When double-clicked, server returns edit form: -->
<form id="title-{{ source.id }}"
      hx-patch="/api/sources/{{ source.id }}/title"
      hx-swap="outerHTML"
      class="flex gap-2">
  <input type="text" name="title" value="{{ source.title }}" 
         class="border rounded px-2 py-1 flex-1" autofocus>
  <button type="submit" class="bg-blue-500 text-white px-3 py-1 rounded">Save</button>
  <button hx-get="/api/sources/{{ source.id }}/title-display" 
          hx-target="#title-{{ source.id }}"
          hx-swap="outerHTML"
          class="text-gray-500 px-3 py-1">Cancel</button>
</form>
```

When title is edited → creates feedback entry for Tier 2 loop.

---

## 3. Feedback Loop Implementation (Three Tiers)

### Tier 1: Automated Self-Healing (in pipeline nodes)

```python
# app/pipeline/nodes/classify.py

async def classify_section(section, llm_client, prompt_manager):
    """
    Tier 1 automated recovery:
    1. Try local model with current prompt (includes any few-shot examples)
    2. If parse fails → retry with strict prompt variant
    3. If confidence < 0.6 → escalate to cloud model
    """
    prompt = await prompt_manager.get_active_prompt("classify")
    formatted = prompt.format(section_content=section["content"])
    
    # Attempt 1: Local model
    try:
        result = await llm_client.generate(formatted, task="classify")
        parsed = parse_llm_json(result)
    except (ValueError, json.JSONDecodeError):
        # TIER 1 LOOP 1A: Parse failure → retry with strict variant
        strict_prompt = await prompt_manager.get_strict_variant("classify")
        formatted_strict = strict_prompt.format(section_content=section["content"])
        try:
            result = await llm_client.generate(formatted_strict, task="classify")
            parsed = parse_llm_json(result)
        except Exception as e:
            return {
                **section,
                "domain": "not_relevant",
                "confidence": 0.0,
                "reasoning": f"Classification failed after retry: {str(e)}",
                "needs_review": True,
            }
    
    # TIER 1 LOOP 1B: Low confidence → escalate to cloud
    if parsed.get("confidence", 0) < 0.6:
        try:
            cloud_result = await llm_client.generate(formatted, task="classify_escalation")
            cloud_parsed = parse_llm_json(cloud_result)
            if cloud_parsed.get("confidence", 0) > parsed.get("confidence", 0):
                parsed = cloud_parsed
                parsed["escalated_to_cloud"] = True
        except Exception:
            pass  # Keep local result if cloud fails
    
    return {
        **section,
        "domain": parsed["domain"],
        "confidence": parsed["confidence"],
        "reasoning": parsed.get("reasoning", ""),
        "needs_review": parsed.get("confidence", 0) < 0.6,
    }
```

### Tier 2: Prompt Evolution from Feedback

```python
# app/services/prompt_evolution.py

class PromptEvolutionService:
    REBUILD_THRESHOLD = 5
    MAX_FEW_SHOT_EXAMPLES = 5
    
    async def process_classification_correction(self, section_id, original_domain, correct_domain, section_content):
        # 1. Store correction in few_shot_bank
        await self.db.add_few_shot_example(
            task_type="classify",
            input_text=section_content[:500],
            original_output={"domain": original_domain},
            corrected_output={"domain": correct_domain},
        )
        
        # 2. Check threshold → rebuild prompt
        active_examples = await self.db.count_few_shot_examples("classify")
        if active_examples >= self.REBUILD_THRESHOLD:
            await self._rebuild_classification_prompt()
    
    async def _rebuild_classification_prompt(self):
        examples = await self.db.get_diverse_few_shot_examples("classify", self.MAX_FEW_SHOT_EXAMPLES)
        
        few_shot_block = "Here are examples of correct classifications:\n\n"
        for ex in examples:
            few_shot_block += (
                f'Section excerpt: "{ex.input_text[:200]}..."\n'
                f'Correct classification: {json.dumps(ex.corrected_output)}\n\n'
            )
        
        base_prompt = CLASSIFY_BASE_PROMPT
        new_prompt = base_prompt.replace("{few_shot_examples}", few_shot_block)
        
        version_hash = hashlib.sha256(new_prompt.encode()).hexdigest()[:12]
        await self.db.save_prompt_version(
            prompt_name="classify",
            version_hash=version_hash,
            content=new_prompt,
            few_shot_examples=[e.to_dict() for e in examples],
        )
    
    async def process_title_correction(self, source_id, new_title, old_title):
        source = await self.db.get_source(source_id)
        await self.db.add_few_shot_example(
            task_type="title",
            input_text=f"Domains: {source.metadata.get('domain_breakdown', '')}",
            original_output={"title": old_title},
            corrected_output={"title": new_title},
        )
    
    async def process_report_rating(self, report_id, rating):
        report = await self.db.get_report(report_id)
        await self.db.record_feedback(
            target_type="report",
            target_id=report_id,
            rating=rating,
        )
```

### Prompt Manager

```python
# app/pipeline/prompts/manager.py

class PromptManager:
    async def get_active_prompt(self, task_name: str) -> str:
        version = await self.db.get_active_prompt_version(task_name)
        if version:
            return version.content
        return self._get_base_prompt(task_name)
    
    async def get_strict_variant(self, task_name: str) -> str:
        base = await self.get_active_prompt(task_name)
        return base + STRICT_SUFFIX
    
    async def get_prompt_version_hash(self, task_name: str) -> str:
        version = await self.db.get_active_prompt_version(task_name)
        return version.version_hash if version else "base"
    
    def _get_base_prompt(self, task_name: str) -> str:
        module = importlib.import_module(f"app.pipeline.prompts.{task_name}")
        return module.PROMPT_TEMPLATE

STRICT_SUFFIX = """

CRITICAL: You MUST respond with ONLY a valid JSON object. No markdown, no backticks, 
no explanation, no preamble. Just the JSON object starting with { and ending with }.
"""
```

---

## 4. Classification Prompt Template

```python
# app/pipeline/prompts/classify.py

PROMPT_TEMPLATE = """
Classify the following transcript section into exactly one domain:

DOMAINS:
- dev_tooling: Development process, tools, frameworks, coding practices, IDE tips, deployment, testing
- ai_solutions: AI implementation, architecture, solutions design, RAG, agents, LLMs, ML pipelines
- business_dev: Business growth, sales, marketing, ROI, pricing, client acquisition, case studies
- not_relevant: Off-topic, personal anecdotes, housekeeping, Q&A logistics

BOUNDARY RULES:
- "Pricing AI solutions" → business_dev (about business strategy)
- "Technical architecture of a RAG system" → ai_solutions (about implementation)
- "How to sell RAG to enterprise clients" → business_dev (about selling)
- When in doubt: BUILD something = ai_solutions/dev_tooling, SELL/GROW something = business_dev

{few_shot_examples}

Section to classify:
{section_content}

Respond with ONLY a JSON object:
{{"domain": "<domain>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}}
"""
```

---

## 5. Feedback Widget (HTMX)

```html
<!-- templates/components/feedback_widget.html -->
<div id="feedback-{{ target_type }}-{{ target_id }}" class="flex items-center gap-3 mt-2">
  <div class="flex gap-1">
    <button hx-post="/api/feedback"
            hx-vals='{"target_type": "{{ target_type }}", "target_id": "{{ target_id }}", "rating": 1}'
            hx-target="#feedback-{{ target_type }}-{{ target_id }}"
            hx-swap="outerHTML"
            class="p-1 rounded hover:bg-green-100">👍</button>
    <button hx-post="/api/feedback"
            hx-vals='{"target_type": "{{ target_type }}", "target_id": "{{ target_id }}", "rating": 0}'
            hx-target="#feedback-{{ target_type }}-{{ target_id }}"
            hx-swap="outerHTML"
            class="p-1 rounded hover:bg-red-100">👎</button>
  </div>
  
  {% if show_correction %}
  <select hx-post="/api/feedback"
          hx-vals='{"target_type": "{{ target_type }}", "target_id": "{{ target_id }}", "rating": 0}'
          hx-include="this" name="correction_domain"
          class="text-sm border rounded px-2 py-1 hidden"
          id="correction-{{ target_id }}">
    <option value="">Correct domain...</option>
    {% for opt in correction_options %}
    <option value="{{ opt }}">{{ opt }}</option>
    {% endfor %}
  </select>
  {% endif %}
</div>

<script>
  // ONE place where minimal JS is acceptable: show correction UI after thumbs down
  document.querySelectorAll('[title="This is wrong"]').forEach(btn => {
    btn.addEventListener('htmx:beforeRequest', (e) => {
      const correction = btn.closest('[id^="feedback-"]').querySelector('[id^="correction-"]');
      if (correction) correction.classList.remove('hidden');
    });
  });
</script>
```

---

## 6. Feedback API Endpoint

```python
# app/api/feedback.py

@router.post("/api/feedback")
async def submit_feedback(target_type, target_id, rating, correction_domain=None, notes=None):
    correction = None
    
    if target_type == "classification" and correction_domain:
        section = await db.get_section(target_id)
        correction = {"correct_domain": correction_domain}
        await prompt_evolution.process_classification_correction(
            section_id=target_id,
            original_domain=section.domain,
            correct_domain=correction_domain,
            section_content=section.content,
        )
    
    if target_type == "report":
        await prompt_evolution.process_report_rating(target_id, rating)
    
    await db.record_feedback(
        target_type=target_type, target_id=target_id,
        rating=rating, correction=correction, notes=notes,
    )
    
    return templates.TemplateResponse(
        "fragments/feedback_confirmed.html",
        {"target_type": target_type, "target_id": target_id,
         "correction_applied": correction is not None},
    )
```

---

## 7. Report Generation with Model Tracking

```python
async def generate_domain_report(sections, domain, llm_client, prompt_manager):
    prompt_name = f"report_{domain}"
    prompt = await prompt_manager.get_active_prompt(prompt_name)
    prompt_version = await prompt_manager.get_prompt_version_hash(prompt_name)
    model = settings.get_model_for_task("report")
    
    formatted = prompt.format(
        sections_text="\n\n".join(s["content"] for s in sections),
        business_context=BUSINESS_CONTEXT,
    )
    
    result = await llm_client.generate(formatted, task="report")
    parsed = parse_llm_json(result)
    
    return {
        **parsed,
        "domain": domain,
        "model_used": model,           # REQUIRED for Tier 3
        "prompt_version": prompt_version,  # REQUIRED for Tier 3
    }
```

---

## 8. Business Context (Injected into All Prompts)

```python
BUSINESS_CONTEXT = """
You are generating insights for the owner of a custom software development company 
based in Louisiana with clients in Dallas and Houston. The company has 15 developers 
(mostly in India) and is transitioning to also offer AI solutions alongside traditional 
custom software. The owner needs actionable intelligence, not academic summaries.

When analyzing content, always consider:
- How does this apply to a 15-dev custom software shop?
- What's the revenue/growth opportunity here?
- What would it take to implement this? (people, time, money)
- Is this relevant NOW or is it future speculation?
"""
```

---

## 9. Contextual Chunking (Phase 2)

```python
# app/services/chunking.py
from langchain_text_splitters import RecursiveCharacterTextSplitter

def create_contextual_chunks(knowledge_entry, chunk_size=512, chunk_overlap=64):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=lambda t: len(t.split()),
    )
    
    raw_chunks = splitter.split_text(knowledge_entry.educational_content)
    
    context_prefix = (
        f"[Source: {knowledge_entry.source_title} | "
        f"Domain: {knowledge_entry.domain} | "
        f"Topic: {knowledge_entry.title}]\n\n"
    )
    
    return [{
        "chunk_index": i,
        "chunk_text": text,
        "context_summary": context_prefix,
        "text_for_embedding": context_prefix + text,  # THIS gets embedded
        "domain": knowledge_entry.domain,
        "source_title": knowledge_entry.source_title,
        "section_title": knowledge_entry.title,
        "tags": knowledge_entry.tags,
    } for i, text in enumerate(raw_chunks)]
```

---

## 10. Hybrid Retrieval (BM25 + Vector + RRF) (Phase 3)

```python
# app/services/retrieval.py

async def hybrid_search(query, query_embedding, top_k=5, domain_filter=None, rrf_k=60):
    async with async_session() as session:
        params = {"query": query, "embedding": query_embedding, "limit": top_k * 2}
        domain_clause = "AND domain = :domain" if domain_filter else ""
        if domain_filter:
            params["domain"] = domain_filter
        
        bm25 = await session.execute(text(f"""
            SELECT id, chunk_text, context_summary, domain, source_title, section_title,
                   ts_rank(search_text, plainto_tsquery('english', :query)) as score
            FROM knowledge_chunks
            WHERE search_text @@ plainto_tsquery('english', :query) {domain_clause}
            ORDER BY score DESC LIMIT :limit
        """), params)
        
        vector = await session.execute(text(f"""
            SELECT id, chunk_text, context_summary, domain, source_title, section_title,
                   1 - (embedding <=> :embedding::vector) as score
            FROM knowledge_chunks WHERE 1=1 {domain_clause}
            ORDER BY embedding <=> :embedding::vector LIMIT :limit
        """), params)
        
        # Reciprocal Rank Fusion
        scores = {}
        for rank, row in enumerate(bm25.mappings().all()):
            cid = str(row["id"])
            scores[cid] = scores.get(cid, {"data": dict(row), "score": 0})
            scores[cid]["score"] += 1.0 / (rrf_k + rank + 1)
        for rank, row in enumerate(vector.mappings().all()):
            cid = str(row["id"])
            scores[cid] = scores.get(cid, {"data": dict(row), "score": 0})
            scores[cid]["score"] += 1.0 / (rrf_k + rank + 1)
        
        return [s["data"] for s in sorted(scores.values(), key=lambda x: x["score"], reverse=True)[:top_k]]
```

---

## 11. Embedding Consistency (CRITICAL)

```python
# app/services/embedding.py

class EmbeddingService:
    """ONE model, ONE service, EVERYWHERE."""
    
    MODEL = settings.OLLAMA_MODEL_EMBED
    EXPECTED_DIMENSION = 768
    
    async def embed(self, text: str) -> list[float]:
        vector = await self.llm_client.embed(text)
        if not self._verified:
            if len(vector) != self.EXPECTED_DIMENSION:
                raise RuntimeError(f"Dimension mismatch: expected {self.EXPECTED_DIMENSION}, got {len(vector)}")
            self._verified = True
        return vector
    
    async def embed_for_storage(self, chunk: dict) -> list[float]:
        return await self.embed(chunk["text_for_embedding"])
    
    async def embed_query(self, query: str) -> list[float]:
        return await self.embed(query)  # SAME model as storage
```

---

## 12. Testing Strategy

- **Unit tests**: Each pipeline node with mock LLM responses
- **Integration tests**: Full pipeline with a short YouTube video
- **Prompt tests**: Sample excerpts with expected classifications
- **Tier 1 loop tests**: Verify parse failure → retry → escalation chain works
- **Tier 2 loop tests**: Verify feedback → few_shot_bank → prompt rebuild → new version active
- **Embedding consistency test**: Same input → same vector
- **Retrieval test** (Phase 3): Known queries → expected chunks
