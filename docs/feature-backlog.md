# Feature Backlog

Theme tags (closed set): UX, Correctness, Performance, Reliability, Security, Architecture, Data, DX, Ops, Cost.

## Shipped

| Feature | Status | Themes | Notes |
|---------|--------|--------|-------|
| CLI interface (`cli.py`) | Shipped 2026-08-12 | DX, UX | `setup-data` / `ingest` / `query` / `eval` / `verify` subcommands; argparse, no new deps |
| Query observability envelope | Shipped 2026-08-12 | UX, Ops | `top_k`, token usage (labeled `estimated-tiktoken`), latency, retrieved chunks, models, timestamp; `--json` flag |
| Expanded regional corpus | Shipped 2026-08-12 | Data, UX | 6 addenda grown ~11–15 → 60–64 lines each; new sections 4.4–4.9; all 8 known-answer facts preserved |
| Idempotent ingestion | Shipped 2026-08-12 | Data, Reliability | `run_ingestion(fresh=True)` wipes `chroma_db/` + `storage/` before rebuild; `ingest --keep` to append |
| `.gitignore` for secrets + derived stores | Shipped 2026-08-12 | Security, DX | `.env`, `__pycache__/`, `chroma_db/`, `storage/` no longer committable |

## Backlog

| Item | Priority | Themes | Notes |
|------|----------|--------|-------|
| `api.py` rebuilds embedding model + index on every HTTP request | High | Performance, Ops | Cache one query engine; rebuild only when the region filter changes |
| Silent `MockLLM` fallback when `GEMINI_API_KEY` missing | High | Reliability, UX | Answers become random text without failing; should hard-fail or return an explicit degraded status |
| Token counts are tiktoken estimates, not provider-reported | Medium | Correctness, Ops | Gemini integration does not reliably surface usage metadata; revisit after SDK migration |
| `google.generativeai` SDK is deprecated (FutureWarning) | Medium | Reliability, Ops | Migrate to the `google.genai`-based llama-index integration |
| `chunker.py` hardcodes `policy_id = "HR-207"` | Low | Architecture | Breaks if a second policy family is added; parse from section header instead |
| API does not expose the observability envelope | Low | UX | `/chat` still returns answer-only; consider a `/chat/detailed` or response flag |
