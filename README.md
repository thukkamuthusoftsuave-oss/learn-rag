# HR-207 Policy RAG

A retrieval-augmented generation pipeline that answers questions about the HR-207 leave-policy addenda (PTO carry-over, sabbaticals) across 6 regions — with citations, metadata-filtered retrieval, and forced refusal for out-of-corpus questions.

## Why

Regional policy addenda look almost identical but differ in the numbers that matter (carry-over caps, eligibility definitions, expiry dates). A naive keyword search returns the wrong region's rule with high confidence. This project demonstrates three things:

1. **Chunking strategy is measurable.** Structure-aware section chunking beats naive line-splitting 8/8 vs 1/8 on hit-in-top-5 (see `results.md` §2).
2. **Metadata filtering changes the answer.** Filtering by `region` moves the correct region's section to rank 1 (see `results.md` §3).
3. **Refusal is forced, not suggested.** The prompt mandates an exact refusal sentence when the answer is not in the corpus, so out-of-domain questions get a deterministic "cannot answer" instead of a hallucination.

## What

- **Corpus**: 6 synthetic addenda (`data/addendum_*.txt`, 60–64 lines each) following a strict format: `Region:` / `Effective Date:` headers + `HR-207 Section X.Y - Title` sections (4.1 Eligibility, 4.2 Carry-over Cap, 4.3 Sabbatical in EMEA/UK only, 4.4–4.9 supplementary rules).
- **Index**: llama-index `HierarchicalNodeParser` (parent/child chunks) → leaf nodes embedded with `BAAI/bge-small-en-v1.5` into ChromaDB (`./chroma_db`), docstore persisted to `./storage`.
- **Query**: `AutoMergingRetriever` (child hits merged into parent context, top-k=5 default) with optional `ExactMatchFilter` on region → Gemini (`models/gemini-flash-latest`) under a citation-enforcing prompt.
- **Interfaces**: CLI (`cli.py`, primary) and FastAPI (`api.py`, `/chat`, `/health`).

## How

### Setup

```powershell
pip install -r requirements.txt
# create .env with:  GEMINI_API_KEY=your_key
python cli.py setup-data   # generate the corpus
python cli.py ingest       # build the index (wipes old stores; --keep to append)
```

### CLI usage

```powershell
python cli.py query "What is the carry-over cap for a probationary employee?" --region US
python cli.py query "Who is eligible for the sabbatical in UK?" --json
python cli.py eval      # chunker bake-off, hit-in-top-5
python cli.py verify    # refusal + region-filter + bonus-scenario checks
```

`query` prints the answer plus a PARAMETERS block: `top_k`, token usage (`estimated-tiktoken`), latency, retrieved chunks with scores, models, timestamp. `--json` emits the same envelope as JSON.

### API (legacy interface, unchanged)

```powershell
python api.py   # serves on :8000 — POST /chat {"query": "...", "region": "US"}
```

### Evaluation

`python cli.py eval` reads the corpus from `data/` (single source of truth) and compares naive vs structure-aware chunking with TF-IDF + cosine over the 8 pre-written known-answer questions. Full results, transcripts, and the chunker decision are in `results.md`; feature history is in `docs/feature-backlog.md`.

## Project layout

```
cli.py        CLI entry point (all subcommands)
setup_data.py corpus generator (single source of truth for data/)
ingest.py     index builder: run_ingestion(fresh=True)
retriever.py  query engine + observability envelope (query_rag)
eval.py       offline chunker evaluation (reads data/)
verify.py     end-to-end smoke checks
api.py        FastAPI wrapper (answer-only)
chunker.py    naive + structure-aware chunkers (eval track)
data/         generated addenda
results.md    quantitative evaluation + transcripts
docs/         feature backlog and design notes
```
