# SQUAD PLAN
**Task:** Convert the HR RAG project into a CLI tool; substantially expand the 6 regional addenda; enrich every query response with operational parameters (top_k, token usage, latency, retrieved chunks, etc.)
**Date:** 2026-08-12
**Status:** AWAITING APPROVAL
**Mode:** SEQUENTIAL
**Base Commit:** c4e2215e89947c8833a980a51d85636bc3f7e0c6

---

## Strategic Direction
Add a CLI as the primary interface while keeping `api.py` working untouched; expand the corpus strictly inside the existing HR-207 format contract so all 8 known-answer eval questions and 3 refusal cases remain valid; instrument the query path with a response envelope (answer + top_k + token counts + latency + retrieved chunks). Re-indexing wipes `chroma_db/` + `storage/` — destructive but fully reproducible from `data/`.

---

## Execution Overview
| Field | Value |
|-------|-------|
| Total Workers | 3 |
| Global Loop Cap | 8 total agent loops max before escalation |
| Est. Handoff Size per Worker | ~1,000-2,000 tokens |
| Irreversible Actions Present | NO (index wipe is reproducible; approved in Phase 0) |
| Untrusted External Content | NO |

---

## Worker Breakdown

### Worker 1 - Corpus & Ingestion Engineer
| Field | Detail |
|-------|--------|
| Persona | Senior Data Engineer |
| Scope | Rewrite `setup_data.py` with expanded corpus; regenerate `data/*.txt`; refactor `ingest.py` into importable `run_ingestion(fresh: bool = True)` + `main()` guard; wipe + rebuild `chroma_db/` and `storage/` |
| Tools | code / write / shell |
| Agent Type | coder |
| Depends On | none |
| Execution | SEQUENTIAL (1st) |
| Reversible | YES - data + index are reproducible artifacts |
| Touches Untrusted Content | NO |

**Content contract (hard constraints):**
- Keep header format `Region:` / `Effective Date:` and section headers `HR-207 Section X.Y - Title`
- Byte-preserve all 8 known-answer facts from the current corpus (cap tables 4.2, US 40hr/52wk definition in 4.1, EMEA/UK 4.3 sabbaticals, LATAM effective date)
- Each file grows to ~60-120 lines: add sections such as 4.4 Carry-over Expiry, 4.5 Payout on Termination, 4.6 Negative Balance, 4.7 Part-time Rule, 4.8 Approval Procedure (region-specific values)
- Forbidden everywhere: "maternity", "home office" reimbursement, any LATAM/NA/APAC/US sabbatical section (refusal cases must stay refusals)
- US part-time content must NOT contradict the bonus scenario (20hr/wk does not meet continuous service)

**Definition of Done:**
- [ ] 6 data files regenerated; each ≥ 60 lines; format contract intact (verified by re-running chunker over files)
- [ ] `python setup_data.py` and `python ingest.py` both work standalone; `run_ingestion(fresh=True)` importable without side effects
- [ ] Ingest is idempotent: wipe+rebuild produces a clean index (report leaf/total node counts before vs after)
- [ ] Forbidden strings absent (`Select-String` check); all 8 known-answer facts present
- [ ] No edits outside `setup_data.py`, `data/`, `ingest.py`

**Output Contract** (max 1,000-2,000 tokens passed forward):
- Delivers: section inventory per region, node counts (before/after), ingest entry-point signature
- Format: handoff contract text
- Next worker needs: `run_ingestion(fresh: bool)` signature + confirmation corpus is indexed

---

### Worker 2 - CLI & Instrumentation Engineer
| Field | Detail |
|-------|--------|
| Persona | Senior Backend/Platform Engineer |
| Scope | New `cli.py` (argparse, stdlib — no new deps); refactor `retriever.py` (`top_k` param, `query_rag(..., detailed=False)` returning envelope dict when detailed); refactor `eval.py` to read corpus from `data/` (kills inline duplicate docs) + `main()` guard; refactor `verify.py` into `run_verification()` + `main()` guard; keep `api.py` byte-identical and working |
| Tools | code / write / shell |
| Agent Type | coder |
| Depends On | Worker 1 |
| Execution | SEQUENTIAL (2nd) |
| Reversible | YES - code only |
| Touches Untrusted Content | NO |

**Envelope schema (returned by `query_rag(..., detailed=True)`):**
`answer`, `is_refusal` (bool, exact-string match), `region`, `top_k`, `retrieved_chunks` [{node_id, score, source_file}], `tokens` {prompt, completion, total, method: "estimated-tiktoken" | "api-reported"}, `latency_ms`, `llm_model`, `embed_model`, `timestamp`

**CLI surface:** `python cli.py setup-data | ingest [--keep] | query "<q>" [--region R] [--top-k N] [--json] | eval | verify`
- `query` prints the answer, then a labeled PARAMETERS block; `--json` prints the raw envelope
- Token counts via llama-index `TokenCountingHandler`; honestly labeled estimated unless Gemini usage metadata is present

**Definition of Done:**
- [ ] All 5 subcommands run; `query` prints answer + PARAMETERS block; `--json` emits valid JSON
- [ ] `query_rag()` default return is still `str` — `api.py` untouched and importable
- [ ] `eval.py` loads docs from `data/` (no inline corpus), still runs standalone
- [ ] No new entries in `requirements.txt` (argparse is stdlib)
- [ ] No edits outside `cli.py`, `retriever.py`, `eval.py`, `verify.py`

**Output Contract:**
- Delivers: CLI command surface, envelope JSON example, entry-point signatures (`run_ingestion`, `run_evaluation`, `run_verification`)
- Next worker needs: exact commands to validate + envelope schema

---

### Worker 3 - Validation & Documentation Engineer
| Field | Detail |
|-------|--------|
| Persona | QA Lead + Technical Writer |
| Scope | Run full validation (`eval`, `verify`, CLI smoke tests incl. region filter + refusal + bonus scenario); update `results.md` with actual observed numbers; create `README.md` (why/what/how, setup, CLI usage, quantitative eval, envelope example); create `docs/feature-backlog.md` with theme-tagged rows; add `.gitignore` (`.env`, `__pycache__/`, etc.) |
| Tools | code / write / shell / analyze |
| Agent Type | coder |
| Depends On | Worker 2 |
| Execution | SEQUENTIAL (3rd) |
| Reversible | YES - docs + validation runs |
| Touches Untrusted Content | NO (Gemini responses are model output, read-only) |

**Definition of Done:**
- [ ] `eval` re-run on expanded corpus; structure-aware ≥ naive; actual scores recorded honestly in `results.md` (target 8/8; report actuals either way)
- [ ] `verify` passes: refusal on maternity leave, US region-filtered answer cites US chunk, bonus scenario behavior documented as observed
- [ ] CLI smoke: ingest from clean state → query with/without region → `--json` parses → eval → verify, all captured in `results.md`
- [ ] `README.md` + `docs/feature-backlog.md` (theme tags: UX, DX, Data, Performance) created; `.gitignore` present and `.env` confirmed ignored (`git check-ignore -v .env`)
- [ ] No edits to `chunker.py`, `api.py`

**Output Contract:**
- Delivers: validation results table, files created/updated list, any failures with evidence
- Next worker needs: n/a (feeds Critic/Verifier)

---

## Execution Trace
| Worker | Status | Loop # | Notes |
|--------|--------|--------|-------|
| Worker 1 | DONE | 3 | 2 subagent dispatches timed out (0 bytes written); orchestrator executed scope inline. Corpus 60-64 lines/file, all facts preserved, fresh index: 74 total / 62 leaf nodes |
| Worker 2 | DONE | 3 | Executed inline. All 5 subcommands verified live; envelope complete; api.py untouched |
| Worker 3 | DONE | 3 | Executed inline. verify 3/3 correct incl. bonus scenario now answering 0 days via Section 4.7; results.md/README/backlog/.gitignore delivered |

---

## Risk Flags
| # | Risk | Decision Made |
|---|------|---------------|
| 1 | Expanded corpus may shift TF-IDF eval scores off 8/8 | Report actuals honestly; smart must stay ≥ naive; investigate if smart < 7/8 |
| 2 | Gemini usage metadata may be unavailable | Fallback to TokenCountingHandler, labeled "estimated-tiktoken" |
| 3 | Index wipe destroys current chroma_db/storage | Approved Phase 0; reproducible via ingest |
| 4 | Gemini rate limits/cost during validation | Bounded: ~8 queries total across verify + smoke tests |
| 5 | `eval.py` inline corpus duplicated `setup_data.py` | Fix at source: eval reads `data/` (single writer) |
| 6 | `.env` could be committed by `git add .` | `.gitignore` lands in Worker 3, before final commit |
| 7 | Orchestrator performs final local commit after Phase 4.5 | Traceability rule; no push |

---

## Approval

**Approve:** `yes` or `go`
**Adjust a worker:** `adjust worker [N]: [feedback]`
**Add a worker:** `add worker: [description]`
**Remove a worker:** `remove worker [N]`
**Restart plan:** `replan`

> No workers spin up until you explicitly approve.
