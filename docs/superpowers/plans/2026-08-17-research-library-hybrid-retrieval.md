# Research Library Hybrid Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retrieve relevant, rights-eligible research evidence through metadata filtering, PostgreSQL full-text search, semantic vectors, deterministic fusion, and a safe lexical fallback.

**Architecture:** Build publication-owned chunks from immutable content. Query candidates are filtered by public eligibility and requested scope before ranking. PostgreSQL uses `tsvector` plus pgvector; SQLite and deployments without the extension use the same metadata boundary with deterministic lexical scoring. ResearchService continues to validate every response and cite only returned evidence.

**Tech Stack:** PostgreSQL full-text search, pgvector, SQLAlchemy 2, existing embedding-provider contract, FastAPI, pytest.

---

## Scope and ordering

This is plan 3 of 4. Start after the core catalog and proof-corpus publication plans. Preserve the existing `retrieve_research_evidence` contract until the final integration task.

### Task 1: Add vector capability preflight and schema

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/alembic/versions/0017_research_chunk_search.py`
- Create: `backend/app/research_library/search_capabilities.py`
- Create: `backend/tests/research_library/test_search_capabilities.py`

- [ ] Write failing tests proving PostgreSQL with the vector extension reports hybrid mode, missing extension reports lexical mode, SQLite reports lexical mode, and `require_vector_search=True` fails startup when unavailable.
- [ ] Add settings:

```python
research_vector_dimensions: int = 1536
require_vector_search: bool = False
research_hybrid_search_enabled: bool = True
```

- [ ] Implement a preflight returning `SearchCapabilities(vector_available, full_text_available, mode, reason)` and call it during application-state wiring without making test SQLite fail.
- [ ] Add migration `0017`: PostgreSQL executes `CREATE EXTENSION IF NOT EXISTS vector`, adds `search_document tsvector`, `embedding vector(1536)`, a GIN index, and an HNSW cosine index. SQLite migration adds nullable text-compatible columns solely for migration-test parity and never claims vector support.
- [ ] Run `uv run pytest backend/tests/research_library/test_search_capabilities.py backend/tests/test_production_configuration.py -q`.
- [ ] Commit with `git add backend/app/config.py backend/app/research_library/search_capabilities.py backend/alembic/versions/0017_research_chunk_search.py backend/tests/research_library/test_search_capabilities.py && git commit -m "feat: add research search capabilities"`.

### Task 2: Build deterministic publication chunks

**Files:**
- Create: `backend/app/research_library/chunking.py`
- Create: `backend/tests/research_library/test_chunking.py`

- [ ] Write failing tests for verse-sized Scripture chunks, section-aware 1 Enoch chunks, chapter-aware Jubilees chunks, overlap limits, token bounds, stable checksums, and no cross-publication chunk.
- [ ] Run `uv run pytest backend/tests/research_library/test_chunking.py -q` and confirm failures.
- [ ] Implement a pure chunker with 350 target tokens, 500 hard maximum, and at most 40-token overlap. Never split a citation anchor unless the source unit itself exceeds the hard maximum.

```python
@dataclass(frozen=True, slots=True)
class ChunkDraft:
    publication_id: uuid.UUID
    work_id: str
    division_id: uuid.UUID
    ordinal: int
    text: str
    anchor_ids: tuple[uuid.UUID, ...]
    checksum: str
```

- [ ] Run the tests and confirm stable results across two runs.
- [ ] Commit with `git add backend/app/research_library/chunking.py backend/tests/research_library/test_chunking.py && git commit -m "feat: build deterministic research chunks"`.

### Task 3: Embed and index active publications

**Files:**
- Create: `backend/app/research_library/indexing.py`
- Create: `backend/app/research_library/index_cli.py`
- Create: `backend/tests/research_library/test_indexing.py`

- [ ] Write failing tests using `DemoEmbeddingProvider` for batch sizing, dimension mismatch, idempotent checksum reuse, changed-chunk replacement, provider failure rollback, and lexical-only indexing.
- [ ] Run `uv run pytest backend/tests/research_library/test_indexing.py -q` and confirm failures.
- [ ] Implement `index_publication()` to re-check public eligibility, build chunks, populate normalized search text, embed in bounded batches, verify configured dimensions, and atomically replace only that publication’s chunk set. In lexical mode, save chunks with null embeddings.
- [ ] Implement `python -m app.research_library.index_cli publication --publication-id ... --actor-id ... --database-url ...` and append audit events for start, success, and failure.
- [ ] Run the indexing tests and confirm all pass.
- [ ] Commit with `git add backend/app/research_library/indexing.py backend/app/research_library/index_cli.py backend/tests/research_library/test_indexing.py && git commit -m "feat: index active research publications"`.

### Task 4: Implement rights-first hybrid retrieval

**Files:**
- Create: `backend/app/research_library/retrieval.py`
- Create: `backend/app/research_library/metrics.py`
- Create: `backend/tests/research_library/test_hybrid_retrieval.py`

- [ ] Write failing tests proving disabled/restricted/internal/unapproved sources never appear, even when they have the highest lexical or vector score. Cover source scopes, work filters, language filters, exact citation queries, deterministic tie-breaking, and lexical fallback.
- [ ] Run `uv run pytest backend/tests/research_library/test_hybrid_retrieval.py -q` and confirm failures.
- [ ] Implement candidate filtering before scoring. PostgreSQL queries produce lexical and vector ranks separately, then combine them with reciprocal-rank fusion:

```python
def reciprocal_rank_fusion(
    lexical_ids: Sequence[str], semantic_ids: Sequence[str], k: int = 60
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked in (lexical_ids, semantic_ids):
        for index, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + index)
    return scores
```

Order by fused score descending, then work ID, division ordinal, chunk ordinal, and chunk ID. Return a bounded maximum based on `ResearchDepth`.
- [ ] Map chunks to the existing `ResearchEvidence` shape with publication ID, edition ID, license/attribution metadata, citation anchor, and an `open_target` that Source Inspector can resolve.
- [ ] Record bounded operational measurements for retrieval latency, excluded-source counts, citation-resolution failures, and embedding backlog. Metrics must contain IDs/counts, never source text or user questions.
- [ ] Run the hybrid retrieval tests and confirm all pass.
- [ ] Commit with `git add backend/app/research_library/retrieval.py backend/tests/research_library/test_hybrid_retrieval.py && git commit -m "feat: retrieve eligible research sources"`.

### Task 5: Integrate with grounded Research AI

**Files:**
- Modify: `backend/app/research/retrieval.py`
- Modify: `backend/app/research/router.py`
- Modify: `backend/app/research/schemas.py`
- Modify: `backend/app/research/service.py`
- Modify: `backend/tests/research/test_retrieval.py`
- Modify: `backend/tests/research/test_service.py`
- Modify: `backend/tests/research/test_routes.py`

- [ ] Extend failing research tests so `1-enoch`, `jubilees`, and `all-sources` retrieve proof-corpus content, citations include source/publication identity, and unauthorized publications are excluded.
- [ ] Run `uv run pytest backend/tests/research -q` and confirm failures.
- [ ] Add source metadata to `ResearchSource`:

```python
source_edition_id: uuid.UUID | None = None
publication_id: uuid.UUID | None = None
license_name: str | None = None
attribution: str | None = None
provenance_url: str | None = None
```

- [ ] Replace the generalized path inside `retrieve_research_evidence` with the new retriever while retaining exact-reference and legacy lexical fallback for linked editions not yet indexed. Merge results by stable source ID and never let fallback bypass eligibility.
- [ ] Construct the embedding provider in the research route, embed the query once, and pass the vector into retrieval. If embedding fails, log the provider failure and continue lexical-only; the answer must remain grounded in returned evidence.
- [ ] Update service validation so every claim source ID resolves to a returned eligible source and AI output cannot manufacture rights metadata.
- [ ] Run `uv run pytest backend/tests/research backend/tests/ai -q` and confirm all pass.
- [ ] Commit with `git add backend/app/research backend/tests/research && git commit -m "feat: ground research AI in hybrid library retrieval"`.

### Task 6: Performance, safety, and regression verification

- [ ] Seed at least 10,000 synthetic chunks in disposable PostgreSQL and confirm a deep query returns within the design budget using `EXPLAIN (ANALYZE, BUFFERS)` with eligibility indexes active.
- [ ] Test extension-off mode by disabling `research_hybrid_search_enabled`; confirm answers still cite lexical evidence.
- [ ] Change an active publication to `restricted`, query immediately, and confirm zero results before reindexing.
- [ ] Add an eligibility metadata cache keyed by publication ID and state/version digest; invalidate it from activation, restriction, replacement, and rollback commands. Test that restriction is visible on the next request.
- [ ] Run `uv run pytest backend/tests/research_library backend/tests/research backend/tests/ai -q`.
- [ ] Run `git diff --check` and inspect all raw SQL parameterization.
- [ ] Commit performance/index adjustments with `git commit -am "perf: verify hybrid research retrieval"`.

## Completion criteria

- Rights and visibility are filtered before ranking and again before response construction.
- pgvector improves relevance when available but is never required for a safe answer.
- Research AI cannot cite a chunk that was not returned from an eligible active publication.
- Exact citations, metadata filters, semantic search, lexical search, and deterministic tie-breaking are tested.
