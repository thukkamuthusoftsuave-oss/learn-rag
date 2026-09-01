# Feature Backlog

Theme tags (closed set): UX, Correctness, Performance, Reliability, Security, Architecture, Data, DX, Ops, Cost.

## Shipped

| Feature | Status | Themes | Notes |
|---------|--------|--------|-------|
| CLI interface | Shipped 2026-08-12 | DX, UX | argparse, no new deps; now `corpus` / `ingest` / `chat` / `serve` / `traces` / `eval {retrieval,chunking,quality,smoke}` |
| Query observability envelope | Shipped 2026-08-12 | UX, Ops | `top_k`, token usage (labeled `estimated-tiktoken`), latency, retrieved chunks, models, timestamp; `--json` flag |
| Expanded regional corpus | Shipped 2026-08-12 | Data, UX | 6 addenda grown ~11–15 → 60–64 lines each; new sections 4.4–4.9; all 8 known-answer facts preserved |
| Idempotent ingestion | Shipped 2026-08-12 | Data, Reliability | `run_ingestion(fresh=True)` wipes `chroma_db/` + `storage/` before rebuild; `ingest --keep` to append |
| `.gitignore` for secrets + derived stores | Shipped 2026-08-12 | Security, DX | `.env`, `__pycache__/`, `chroma_db/`, `storage/`, `var/`, `reports/` no longer committable |
| Hybrid retrieval (BM25 + vector, RRF) | Shipped 2026-08-19 | Correctness | Fused with `QueryFusionRetriever` (`num_queries=1`, no extra LLM call); on by default via `RAG_HYBRID`. Measured: hit-rate@1 0.875 → 1.000 on region-explicit questions, but a section-number question regressed rank 1 → 2; see evaluation-results.md §9 |
| Retrieval benchmark | Shipped 2026-08-19 | Correctness, Ops | hit-rate@1/@3 and MRR, vector-only vs hybrid, region-explicit and exact-term sets reported separately |
| Web UI | Shipped 2026-08-19 | UX | Single chat surface: transcript, per-answer sources and observability behind a details toggle, region/hybrid/top-k settings. Evaluation and traces are CLI + API only, deliberately not screens |
| Package layout (`policy_rag/`) | Shipped 2026-08-25 | Architecture, DX | Layered into corpus / indexing / retrieval / chat / observability / evaluation / api; `pyproject.toml` with a `policy-rag` entry point |
| Central configuration | Shipped 2026-08-25 | Ops, DX | `config.py` is the single source of paths, models and prompts; every value env-overridable, relative paths anchored at the project root |
| Trace log for every answer | Shipped 2026-08-25 | Ops, Correctness | UI, CLI and evaluation all answer through `chat.service.answer`, which appends to `var/traces.jsonl`; `policy-rag traces` and `GET /api/traces` read it |
| Error taxonomy as a module | Shipped 2026-08-25 | Correctness, Ops | Labels, severities and remediations defined once in `observability/taxonomy.py`; CLI, API and UI all render the same prediction card |
| Golden question sets in one file | Shipped 2026-08-25 | Correctness, DX | `evaluation/datasets.py`; a question can no longer mean two things in two reports |
| Multi-turn chat | Shipped 2026-08-25 | UX | Follow-ups condensed into standalone questions before retrieval; falls back to the raw question on any failure |
| Cached query engines | Shipped 2026-08-25 | Performance | `lru_cache` per `(region, top_k, hybrid)`; invalidated by re-ingestion. Closes the "rebuilds the index on every request" item |
| Unit tests | Shipped 2026-08-25 | DX, Reliability | Model-free tests for chunking, dataset integrity, taxonomy, the trace log and vector-store selection |
| Pluggable vector-store backend | Shipped 2026-08-25 | Architecture, Ops | `policy_rag/vector_store.py` resolves local `chroma_db/` or hosted Chroma Cloud from `RAG_VECTOR_BACKEND`; indexer and retriever share it, misconfigured cloud fails loudly. Docstore stays local by design |

## Backlog

| Item | Priority | Themes | Notes |
|------|----------|--------|-------|
| Silent `MockLLM` fallback when `GEMINI_API_KEY` missing | High | Reliability, UX | Now labelled in the envelope, health check and every trace, but still does not fail loudly; consider a strict mode |
| Cross-encoder reranker | Medium | Correctness | The named next step whenever the taxonomy ranks generation failures first: `bge-reranker-base` over the fused top-k |
| Token counts are tiktoken estimates, not provider-reported | Medium | Correctness, Ops | Gemini integration does not reliably surface usage metadata; revisit after SDK migration |
| `google.generativeai` SDK is deprecated (FutureWarning) | Medium | Reliability, Ops | Migrate to the `google.genai`-based llama-index integration |
| Region auto-detection from the question | Medium | Correctness, UX | The one failure neither retriever fixes (`HARD-04`): no region named anywhere. Detect and prompt, or ask the user |
| Docstore is local-only | Low | Architecture, Ops | Embeddings can go to Chroma Cloud but `storage/` cannot; a hosted docstore (e.g. MongoDB) would make the app fully stateless |
| Trace log growth is unbounded | Low | Ops | `TraceStore.prune` exists but nothing calls it; add rotation or a retention setting |
| Answer-quality labels assume a correct answer when the source is right | Low | Correctness | `CORRECT` means "right document, plausible answer"; claim-level checking still needs a human or an LLM judge |
| No auth on the API | Low | Security | Fine for local use; anything shared needs at least a token on the evaluation endpoints |
