# HR-207 Policy Assistant

A retrieval-augmented chat assistant that answers questions about the HR-207
leave-policy addenda (PTO carry-over, sabbaticals) across six regions — with
citations, region-filtered hybrid retrieval, a forced refusal for out-of-corpus
questions, and a trace log that every answer is written to.

## Why

Regional policy addenda look almost identical but differ in the numbers that
matter: carry-over caps, eligibility definitions, expiry dates. A naive search
returns the wrong region's rule with total confidence. Three things in this
project exist to stop that, and each one is measured rather than asserted:

1. **Chunking is a measurable decision.** Structure-aware section chunking
   beats naive line splitting 8/8 vs 1/8 on hit-in-top-5
   (`policy-rag eval chunking`).
2. **Retrieval and generation fail differently, so they are measured
   separately.** Hybrid BM25 + vector retrieval, fused with Reciprocal Rank
   Fusion, is scored on hit-rate@1/@3 and MRR against a vector-only baseline
   (`policy-rag eval retrieval`), and the report names what it does *not* fix.
3. **Refusal is forced, not suggested.** The prompt mandates an exact refusal
   sentence when the answer is not in the corpus, so out-of-domain questions
   get a deterministic "cannot answer" instead of an invention.

## What

- **Corpus** — six synthetic addenda (`data/addendum_*.txt`) following a strict
  format: `Region:` / `Effective Date:` headers plus `HR-207 Section X.Y`
  sections (4.1 Eligibility, 4.2 Carry-over Cap, 4.3 Sabbatical in EMEA/UK
  only, 4.4–4.9 supplementary rules). Generated, so it is reproducible.
- **Index** — llama-index `HierarchicalNodeParser` (parent/child chunks), leaf
  nodes embedded with `BAAI/bge-small-en-v1.5` into ChromaDB (`chroma_db/`),
  docstore persisted to `storage/`.
- **Retrieval** — `AutoMergingRetriever` over either the vector retriever alone
  or BM25 + vector fused with RRF (the default), with an optional exact-match
  region filter. Query engines are cached per configuration.
- **Chat** — multi-turn. A follow-up such as "what about the UK?" is condensed
  into a standalone question before retrieval, so context is not lost.
- **Observability** — every answer, from the UI, the CLI or an evaluation run,
  is appended to `var/traces.jsonl` with its retrieved chunks, token usage,
  latency and an automatic label.
- **Interfaces** — a chat UI, an admin console behind the gear icon (index
  rebuilds, every metric, the trace log), a JSON API (`policy-rag serve`) and a
  CLI (`policy-rag chat`).

## Quick start

```powershell
pip install -r requirements.txt      # or: pip install -e .
copy .env.example .env               # then set OPENROUTER_API_KEY

python -m policy_rag corpus          # generate the corpus
python -m policy_rag ingest          # build the index (wipes old stores; --keep to append)
python -m policy_rag serve           # web UI on http://localhost:8000
```

Installing with `pip install -e .` provides a `policy-rag` command; without it,
every command below works as `python -m policy_rag ...`.

## Using it

```powershell
# Interactive conversation (/region US, /reset, /sources, /exit)
policy-rag chat

# One-shot question
policy-rag chat "What is the carry-over cap for a probationary employee?" --region US
policy-rag chat "Who is eligible for the sabbatical in UK?" --json
policy-rag chat "After 10 years what sabbatical do I get?" --no-hybrid

# What the assistant has been asked, and how it did
policy-rag traces --limit 20
policy-rag traces --source chat
```

Every answer prints its sources and a parameter block: region filter, top-k,
retrieval mode, token usage (honestly labelled `estimated-tiktoken`), latency,
models, and the trace id. `--json` emits the same envelope as JSON.

## Evaluating it

| Command | Measures | LLM calls |
|---|---|---|
| `policy-rag eval chunking` | naive vs structure-aware chunking, hit-in-top-5 | none |
| `policy-rag eval retrieval` | vector-only vs hybrid: hit-rate@1, hit-rate@3, MRR | none |
| `policy-rag eval quality` | what the assistant answers: traces → taxonomy → prediction card | one per question |
| `policy-rag eval smoke` | three end-to-end checks: refusal, region filter, edge case | three |

`eval quality` runs the golden suite through the **same** answer path the UI
uses, labels each trace (retrieval failure, generation failure, correct
refusal, …), ranks the problem types by frequency × severity, and writes
`reports/answer-quality.md` ending in a single prediction card: the one change
to make next, what it should move, and what it will not fix. Rebuild that
report from stored traces without spending any calls with
`policy-rag eval quality --from-traces`.

It paces itself at one question every 2 seconds (`RAG_EVAL_PAUSE_SECONDS`).
Raise that setting if your selected OpenRouter model or account has a lower
per-minute ceiling. Pacing cannot help with a daily allowance; when a provider
reports one, the run stops rather than recording unasked questions as failures.

```powershell
pytest        # chunking, dataset integrity, taxonomy and trace-log tests
```

## HTTP API

| Route | Purpose |
|---|---|
| `GET /` | Chat UI |
| `GET /admin` | Admin console (index rebuilds, metrics, traces) |
| `GET /api/health` | Liveness plus the active configuration |
| `POST /api/chat` | Ask a question; returns the full envelope |
| `POST /api/admin/ingest` | Rebuild the index (needs `{"confirm": true}`) |
| `POST /api/admin/corpus` | Regenerate the corpus files |
| `GET /api/admin/status` | Full operator status: stores, corpus, models, traces |
| `GET /api/traces` | Recent traces with their taxonomy |
| `DELETE /api/traces` | Clear the trace log |
| `POST /api/evaluation/retrieval` | Retrieval benchmark (no LLM calls) |
| `POST /api/evaluation/chunking` | Chunking bake-off (no LLM calls) |
| `POST /api/evaluation/smoke` | Three end-to-end checks |
| `POST /api/evaluation/quality` | Answer-quality run |
| `GET /api/evaluation/quality` | Last report, rebuilt from stored traces |

`POST /chat` and `GET /health` remain as aliases for older clients.

## Project layout

```
policy_rag/
  config.py              paths, models, prompts - all env-overridable
  cli.py                 every command
  corpus/                generator.py (writes data/), chunking.py (both strategies)
  indexing/pipeline.py   corpus -> vector store + docstore
  retrieval/engine.py    vector and hybrid retrievers, cached query engines
  chat/                  service.py (the one answer path), session.py (multi-turn)
  observability/         traces.py (the log), taxonomy.py (labels and ranking)
  evaluation/            datasets.py (golden questions) + one module per suite
  api/                   app.py (chat), admin.py (operator routes), schemas.py
  web/static/            index.html (chat) and admin.html (operator console)
data/                    generated corpus
chroma_db/ storage/      derived index artifacts
var/traces.jsonl         trace log
reports/                 generated evaluation reports
docs/                    results, backlog, engineering notes
tests/                   model-free unit tests
```

## Configuration

Everything is set in `.env` (see `.env.example`). The defaults that matter:
`RAG_HYBRID=true` (hybrid retrieval is the shipped default), `RAG_TOP_K=5`,
`RAG_LLM_MODEL=google/gemini-2.5-flash-lite`,
`RAG_EMBED_MODEL=BAAI/bge-small-en-v1.5`. Without `OPENROUTER_API_KEY` the
assistant falls back to a mock LLM and says so in every response and trace.

### Storing embeddings in the cloud

By default the embeddings live in `chroma_db/` on your machine — no account, no
network. To keep them in a hosted [Chroma Cloud](https://trychroma.com)
database instead:

1. Sign up at [trychroma.com](https://trychroma.com) and create a database. Note
   its **name** — that is `CHROMA_DATABASE`.
2. Your **tenant** is the workspace the database belongs to; Chroma shows it
   alongside the database, as a UUID. That is `CHROMA_TENANT`.
3. Create an **API key** and copy it — it starts with `ck-` and is shown once.
   That is `CHROMA_API_KEY`.
4. Put all four values in `.env` (never commit it; `.gitignore` already covers it):

```
RAG_VECTOR_BACKEND=cloud
CHROMA_API_KEY=ck-...
CHROMA_TENANT=...
CHROMA_DATABASE=...
```

5. Re-run `policy-rag ingest`, or press **Rebuild index** in the admin console.
   Confirm it worked on the console's status card: the vector store should read
   *Chroma Cloud* with a non-zero embedded-chunk count.

Then re-run `policy-rag ingest`. Embeddings live wherever they were written, so
switching backends means re-ingesting; `/api/health` reports the active one. If
the backend is `cloud` with a credential missing, ingestion and retrieval fail
with a message naming it rather than silently writing to disk.

**The docstore stays local.** `storage/` is not the vector store: auto-merging
retrieval reads parent sections from it and BM25 builds its keyword index from
its leaf nodes, so it is required in both modes. It is a couple of hundred
kilobytes and `ingest` rebuilds it, which is why it does not justify a second
hosted service.

## Admin console

The gear icon in the chat header opens `/admin`: a separate page for operator
work, kept out of the chat surface on purpose. It shows a status panel (vector
store and its embedded-chunk count, docstore, corpus, models, trace totals,
plus warnings worth acting on) and runs everything from one place: regenerate
the corpus, rebuild the index, all four metric suites, and the trace log.

**It is not authenticated,** and it can rebuild the index and spend LLM calls.
Destructive actions (rebuild, clearing traces) require an explicit confirmation,
and `RAG_ADMIN_ENABLED=false` removes the console and its routes entirely —
set that before exposing the server beyond localhost.

## Troubleshooting

**`No Python at '...'` when running anything in `venv/`.** The venv records an
absolute path to the interpreter that created it, so it breaks when the project
moves machines or users. Install the matching Python version (see
`venv/pyvenv.cfg` for which one) and run `python -m venv --upgrade venv` — this
repoints the venv and keeps every installed package.

**`WinError 1114 ... c10.dll` from torch, or a segfault from chromadb.** Both
ship native code built against the Visual C++ 2015-2022 runtime, and Windows
installs that are only up to the 2019 runtime (msvcp140.dll 14.29) fail on
load. Install the [VC++ 2015-2022 redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)
— it needs administrator rights. As a fallback without admin, copying
`msvcp140.dll`, `vcruntime140.dll`, `vcruntime140_1.dll` and `concrt140.dll`
from a newer app that bundles them (Edge ships 14.44) into
`venv/Lib/site-packages/torch/lib/` and
`venv/Lib/site-packages/chromadb_rust_bindings/` works, because Windows
searches a DLL's own directory first. Prefer the real redistributable.

**The first question after startup takes about a minute.** The embedding model
loads lazily on first use. Every later question is fast; query engines are
cached per `(region, top_k, hybrid)`.

**Answers come back empty, and the trace says `PIPELINE_ERROR ... 429`.** The
selected OpenRouter model or account has hit a rate, credit, or daily limit.
Check the OpenRouter activity page, wait if it is temporary, or select a model
and account with sufficient available capacity. Raise `RAG_EVAL_PAUSE_SECONDS`
before `eval quality` if it is a per-minute limit. The failure is recorded in
the trace rather than hidden behind an empty answer.

## Further reading

- `docs/evaluation-results.md` — full results, transcripts and the chunking decision
- `docs/retrieval-and-error-analysis.md` — engineering notes on hybrid search,
  reranking, traces and error analysis
- `docs/feature-backlog.md` — what shipped and what is next
