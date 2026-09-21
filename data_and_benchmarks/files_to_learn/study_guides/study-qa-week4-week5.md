# Study Q&A — Week 4 M2 (Retrieval Debugging) + Week 5 M3 (Error Analysis)

Every answer below is grounded in this repo. File references are real; numbers come
from `docs/evaluation-results.md` §9 (observed 2026-08-25) and from the code itself.

Where the project **does not** implement a topic the curriculum lists, that is said
plainly rather than papered over — those are your build items, not your talking points.

---

## Part A — Week 4 · Module 2: Retrieval & RAG debugging

### A1. Failure separation (the whole point of the week)

**Q1. What are the two kinds of "wrong", and why can't one fix cover both?**

- **Retrieval failure** — the correct document never reached the model. The model
  answered from the wrong region's addendum, or refused because nothing useful arrived.
- **Generation failure** — the correct document *was* in the context and the answer is
  still wrong (misread cap table, ignored an eligibility clause, refused anyway).

They need opposite fixes. A retrieval failure is fixed by the retriever (BM25, filters,
reranking, rewriting). A generation failure is fixed by the prompt, the reranker's
*ordering*, or a better model. Swapping to a smarter LLM does nothing for a retrieval
failure — the right text was never in the window, so no amount of reasoning recovers it.
You pay more and fix zero.

**Q2. Where does this project actually draw the line, in code?**

`policy_rag/observability/taxonomy.py`, in `classify()`:

```python
retrieval_ok = expected_source is None or expected_source in top_sources  # top 3
```

`top_sources` is `[c["source_file"] for c in retrieved_chunks][:3]`. So the decision rule is:

| Condition | Label |
|---|---|
| `error` set | `PIPELINE_ERROR` |
| no `expected_type` (live traffic) | `UNLABELED` |
| expected refusal, got refusal | `CORRECT_REFUSAL` |
| expected refusal, got an answer | `GENERATION_FAILURE` (hallucination) |
| refused **and** `retrieval_ok` | `GENERATION_FAILURE` (refusal fires too eagerly) |
| refused **and not** `retrieval_ok` | `RETRIEVAL_FAILURE` |
| answered **and** `retrieval_ok` | `CORRECT` |
| answered **and not** `retrieval_ok` | `RETRIEVAL_FAILURE` (confidently wrong region) |

**Q3. Why is "refused" not automatically a retrieval failure?**

Because a refusal has two very different causes. If the expected document *was* in the
top 3 and the assistant still said the refusal sentence, retrieval did its job and the
prompt is over-triggering — that is a generation failure. Only when the expected document
is absent is the refusal caused by retrieval. This project encodes exactly that split;
that branch is the single most quotable piece of code for your mentor review.

**Q4. What is the "decision test" you can run by hand on one failure?**

Look at the trace's `retrieved_chunks`. Ask: *is the text that contains the correct
answer anywhere in there?*
- No → retrieval failure. Stop. Do not touch the prompt.
- Yes → generation failure. Stop. Do not touch the retriever.

That is a two-minute check and it is the evidence your mentor is asking for.

**Q5. What is the known weakness of this project's `CORRECT` label?**

`CORRECT` means "the right document was in the top 3 and the assistant did not refuse".
It does **not** verify the numbers in the answer. The observation string says so:
*"Wording still needs a human read to confirm the numbers."* This is listed in
`docs/feature-backlog.md` as an open item. So a wrong number sourced from the right
document is currently labelled `CORRECT` — a false negative in your error analysis.

---

### A2. Traces and the inspection view

**Q6. What is a trace, and what makes one "complete"?**

A trace is the full record of one request — enough to *replay* it later, not just to read
it. This project's schema is `TRACE_DEFAULTS` in `policy_rag/observability/traces.py`:

`trace_id`, `run_id`, `source`, `session_id`, `query`, `standalone_query`, `region`,
`top_k`, `hybrid`, `answer`, `is_refusal`, `retrieved_chunks`, `top_sources`, `tokens`,
`latency_ms`, `llm_model`, `embed_model`, `timestamp`, `golden_id`, `expected_type`,
`expected_source`, `expected_section`, `label`, `observation`, `retrieval_ok`, `error`.

The replayability test: could you rebuild the exact same run from these fields alone?
Here you can — `region`, `top_k`, `hybrid`, `embed_model` and `llm_model` are all
recorded, so you know which retrieval configuration produced the result.

**Q7. Why is logging only the final answer useless for debugging?**

Because the answer alone cannot distinguish the two failure kinds. "The cap is 15 days"
is wrong in exactly the same way whether the model read the wrong addendum or misread the
right one. Without `retrieved_chunks` you cannot tell, so you cannot choose a fix.

**Q8. Why JSONL, append-only?**

`TraceStore.append` writes one JSON object per line to `var/traces.jsonl`. It is cheap to
tail, trivially diffable, greppable, needs no database, and a partially written final line
does not break reading (`read()` skips `JSONDecodeError` lines). `prune()` rewrites via a
temp file + `os.replace` so an interrupted prune cannot corrupt the log.

**Q9. Why does this project's evaluation write to the *same* trace log as live chat?**

Because the UI, the CLI and every eval suite all call one function —
`policy_rag.chat.service.answer`. That means error analysis reads the real system, not a
parallel offline reimplementation of it. This is the single most important architectural
decision for Week 5: if your eval path differs from your production path, your taxonomy
describes a system that does not exist.

**Q10. Does this project have an inspection view? What's missing?**

Partly. Three surfaces show question → retrieved → answer:
- `policy-rag chat "..."` prints the envelope (`_print_envelope` in `policy_rag/cli.py`)
- `policy-rag traces --limit N`
- the web UI's per-answer sources/observability toggle

What a *proper* inspection view adds and this one lacks: side-by-side before/after for two
retrieval configs on the same question, the full chunk text (only a 160-char preview is
stored), and a place to type a human label. Your `retrieved_chunks[].text_preview` is
truncated to 160 chars — enough to identify a chunk, not enough to verify an answer against it.

**Q11. Trace-integrity gotcha in this codebase — where can token counts lie?**

`_TOKEN_COUNTER` is a single process-wide `TokenCountingHandler` (`retrieval/engine.py`),
and `service.answer` calls `engine.token_counter().reset_counts()` before each query. Under
concurrent API requests, two queries interleave and clobber each other's counts. Fine for
CLI/eval (serial); a real bug for the served API. Also `tokens.method` is
`"estimated-tiktoken"`, not provider-reported — the field labels its own uncertainty,
which is the honest thing to do.

---

### A3. Keyword search (BM25)

**Q12. What is BM25 in one paragraph?**

A bag-of-words lexical ranking function. It scores a document by how often the query's
terms appear in it (term frequency), damped so the 10th occurrence adds less than the 2nd
(saturation), weighted by how rare each term is across the corpus (IDF), and normalised by
document length so long documents don't win by default. It matches *tokens*, not meaning.

**Q13. Keyword vs semantic — one-line differences that matter here.**

| | BM25 (lexical) | Biencoder / vector (semantic) |
|---|---|---|
| Matches | exact tokens | meaning in embedding space |
| `ERR-4032`, `Section 4.8`, `US` | exact hit | blurred with near-neighbours |
| "time off after having a baby" ↔ "parental leave" | miss | hit |
| Out-of-vocabulary / new codes | works immediately | needs the term to be embeddable |
| Index cost | cheap, no model | embedding model + vector store |

**Q14. Why does the HR-207 corpus specifically need BM25?**

Six addenda that are near-identical in wording — same sections, same phrasing, different
numbers and region codes. In embedding space `addendum_US.txt §4.2` and
`addendum_LATAM.txt §4.2` are nearly the same point. The only reliable discriminators are
literal tokens: `US`, `EMEA`, `Section 4.8`, `10 years`, `5 years`. Those are exactly what
BM25 matches and what a biencoder blurs. `docs/evaluation-results.md` §3 shows the failure
directly: unfiltered, the top hit for a US question was the **LATAM** chunk at 0.2006.

**Q15. Why is BM25 alone not enough?**

It cannot match paraphrase. "What happens to my unused days if I quit?" shares almost no
tokens with "forfeiture of accrued carry-over balance upon separation". Semantic search
gets that; BM25 returns nothing useful. You need both, which is why you fuse.

**Q16. This project's BM25 has a limitation the vector side doesn't. What is it?**

BM25 has no native metadata filter. The vector retriever gets
`MetadataFilters([ExactMatchFilter(key="region", ...)])`; BM25 has to mirror that in
Python:

```python
leaf_nodes = get_leaf_nodes(list(storage_context.docstore.docs.values()))
if region:
    leaf_nodes = [n for n in leaf_nodes if (n.metadata or {}).get("region") == region]
```

Two consequences: the BM25 index is **rebuilt per retriever construction** (mitigated only
by the `lru_cache` on the query engine), and the filter logic now exists in two places that
must be kept in agreement.

---

### A4. Hybrid search and RRF

**Q17. What is Reciprocal Rank Fusion, mathematically?**

Each retriever produces a ranked list. For a document appearing at rank *r* in a list, that
list contributes `1 / (k + r)`, with `k` a smoothing constant (60 is the common default).
Sum the contributions across lists; sort descending.

```
RRF(d) = Σ_lists  1 / (k + rank_list(d))
```

**Q18. Why does RRF use ranks instead of scores?**

Because BM25 scores and cosine similarities are not on a comparable scale — BM25 is
unbounded and corpus-dependent, cosine sits in roughly [0, 1] and its useful spread is
narrow (look at §3: 0.2006 vs 0.1921 — a 0.008 gap decides the answer). Normalising them
against each other requires calibration you don't have. Ranks are scale-free, so fusion
works out of the box. The cost: you throw away confidence. A rank-1 hit at cosine 0.95 and
a rank-1 hit at cosine 0.21 contribute identically.

**Q19. Where is hybrid implemented here, and what's the `num_queries=1` about?**

`policy_rag/retrieval/engine.py`, `build_retriever`:

```python
base_retriever = QueryFusionRetriever(
    retrievers=[vector_retriever, _build_bm25_retriever(storage_context, region, top_k)],
    similarity_top_k=top_k,
    mode="reciprocal_rerank",
    num_queries=1,
)
```

`QueryFusionRetriever` by default also generates *query variations* with an LLM call.
`num_queries=1` disables that, so the fusion is purely BM25 + vector — no LLM cost, and no
hidden second variable when you attribute a metric change to "hybrid".

**Q20. What is `AutoMergingRetriever` doing on top, and why does it matter for your metrics?**

Both modes end wrapped in `AutoMergingRetriever(base_retriever, storage_context)`. Chunking
is hierarchical (`CHUNK_SIZES = [512, 128]`), so retrieval hits small 128-token children;
auto-merging replaces a cluster of sibling children with their 512-token parent. This is why
the part-time edge case (§7 of the results doc) resolved — neighbouring sections travel
together. For metrics it means the number of returned nodes can be *fewer* than `top_k`, and
"rank 1" refers to a possibly-merged parent.

**Q21. State this project's actual hybrid result — honestly.**

`top_k=5`, **no region filter** (worst case), `policy-rag eval retrieval`:

| Set | Metric | Vector-only | Hybrid | Δ |
|---|---|---|---|---|
| Region named (n=8) | hit-rate@1 | 0.875 | **1.000** | +0.125 |
| | hit-rate@3 | 1.000 | 1.000 | 0.000 |
| | MRR | 0.938 | **1.000** | +0.063 |
| Exact-term / no region (n=3) | hit-rate@1 | 0.667 | **0.333** | −0.333 |
| | hit-rate@3 | 1.000 | 1.000 | 0.000 |
| | MRR | 0.778 | **0.611** | −0.167 |
| All scorable (n=11) | hit-rate@1 | 0.818 | 0.818 | 0.000 |
| | hit-rate@3 | 1.000 | 1.000 | 0.000 |
| | MRR | 0.894 | 0.894 | 0.000 |

Two questions moved, in opposite directions:
- **CORE-07** (`"...senior with > 2 years of service in US"`): rank **2 → 1**. The literal
  `US` token is a BM25 match, so the right region stops losing to a semantically identical row.
- **HARD-03** (`"...HR-207 Section 4.8 ... in APAC"`): rank **1 → 2**. The case hybrid was
  *predicted* to win, and it lost.

**Q22. Explain the HARD-03 regression — this is the best question you can be asked.**

The vector retriever already had it at rank 1. Fusion cannot preserve that: it averages a
first place against BM25's opinion. And BM25's opinion is bad here, because "Section 4.8"
appears in *every* addendum — the section number is high-IDF against the general corpus but
completely non-discriminative *between* the six documents. So BM25 promotes a competing
addendum, and RRF's rank-only arithmetic lets that outvote a confident vector hit.

Generalised lesson: **fusion is a trade, not a free win.** It helps where one retriever is
blind and hurts where the other was already right.

**Q23. Why not just weight the vector score higher instead of fusing?**

Because of Q18 — the scores aren't comparable, so any weight is a magic number tuned to
your current corpus and embedding model. It silently breaks when you re-embed. If you want
weighting, use a *learned* fusion, which needs labelled training data you don't have at
n=11.

**Q24. Why is hybrid still the shipped default given the aggregate is flat?**

Documented in `config.py` at `DEFAULT_HYBRID`: region-explicit questions are what users
actually ask, and hit-rate@1 = 1.000 there is the metric that decides *what the model reads
first*. The regression is on a 3-question set. Override per query with `--no-hybrid` or
globally with `RAG_HYBRID=false`. Note the config comment ends with "re-measure after any
index change before trusting either number" — that is the right posture at these sample sizes.

---

### A5. Reranking (cross-encoder) — **not implemented here**

**Q25. Biencoder vs cross-encoder — what's the actual difference?**

- **Biencoder**: embeds query and document *separately*, compares with cosine. Documents are
  embedded once at index time, so search is an ANN lookup over millions of vectors. Fast,
  approximate, no query–document interaction.
- **Cross-encoder**: feeds `[query, document]` through a transformer *together* and outputs
  one relevance score. Full attention between query tokens and document tokens, so it can
  tell that "senior, >2 years, **US**" matches this row and not the identical row in LATAM.
  Cannot be precomputed — cost is O(number of candidates) forward passes.

**Q26. What is the two-stage pattern?**

Retrieve wide and cheap (biencoder / hybrid, top-k = 20–50), then rerank narrow and
expensive (cross-encoder over those 20–50), keep the top 3–5 for the context window. You get
cross-encoder precision at biencoder cost, because you only pay the expensive model on
candidates the cheap one already shortlisted.

**Q27. Why not rerank everything?**

A cross-encoder pass is one forward pass per document. Over a 100k-document corpus that is
100k forward passes per query — seconds to minutes, and it defeats the purpose of the vector
index. Reranking is a *reordering* step over a shortlist, never a search step.

**Q28. Which reranker would you use here, and what's the trade?**

| Reranker | Type | Trade |
|---|---|---|
| `BAAI/bge-reranker-base` | local, open | free, ~400 MB, adds ~100–300 ms CPU per query |
| `BAAI/bge-reranker-large` | local, open | better, slower, ~1.3 GB |
| Cohere Rerank v3 | hosted API | strongest, per-call cost, network latency, data leaves your machine |

This repo already names the choice: `taxonomy.REMEDIATION["GENERATION_FAILURE"]["change"]`
prescribes `bge-reranker-base`, and `docs/feature-backlog.md` lists "Cross-encoder reranker"
at Medium priority. **It is not in the code.** `grep -ri rerank policy_rag/` finds only
`mode="reciprocal_rerank"` (which is RRF, not a cross-encoder) and that backlog text.

**Q29. If you add it, where does it go and what should you predict?**

As a `node_postprocessor` on the `RetrieverQueryEngine` in
`engine._cached_query_engine`, after the `AutoMergingRetriever`. You'd raise `top_k` to ~20
so the reranker has candidates to work with, then cut to 3.

Prediction to write down *first*: hit-rate@3 barely moves (already 1.000 — see Q41);
**hit-rate@1 and MRR** are the metrics that can move, plus answer accuracy on table-reading
questions. It will not fix `HARD-04`, which has no correct document at all.

---

### A6. MMR — **not implemented here**

**Q30. What problem does Maximal Marginal Relevance solve?**

Redundancy. Top-k by pure similarity can return five near-duplicate chunks that all say the
same thing, wasting the context window and hiding the one chunk that says something *else*
you need. MMR trades relevance against novelty:

```
MMR = argmax_d [ λ · sim(d, query) − (1 − λ) · max_{s ∈ selected} sim(d, s) ]
```

λ = 1 is plain relevance; λ = 0 is pure diversity; ~0.5–0.7 is typical.

**Q31. Would MMR help this corpus? Be careful.**

Cuts both ways, and you should say so:
- **For**: the six addenda are near-duplicates, so an unfiltered query genuinely can return
  five variants of "Section 4.2" from five regions. MMR would surface different *sections*
  instead.
- **Against**: with a region filter applied, diversity is the wrong objective — you want
  §4.1 (definition) *and* §4.2 (cap) from the **same** addendum, and MMR's penalty term
  could push out the second one precisely because it's from the same document.

Also, `AutoMergingRetriever` already handles part of this by merging siblings into a parent.

**Q32. Why not just increase top-k instead of using MMR?**

More redundant chunks is not more information. You pay tokens and latency, you push the
decisive chunk further from the start of the prompt (position matters), and you raise the
chance the model latches onto a wrong-but-plausible neighbour. Increasing k widens *recall*;
MMR widens *coverage*. Different problems.

---

### A7. Query rewriting and HyDE

**Q33. What query rewriting exists in this project already?**

Conversational condensation — `policy_rag/chat/session.py:condense_question`, driven by
`config.CONDENSE_PROMPT_TEMPLATE`. "What about the UK?" retrieves nothing on its own, so it
is rewritten into a standalone question carrying every concrete detail (region, employee
type, years of service, section numbers) before retrieval. Recorded on the trace as
`standalone_query`, and `None` when no rewrite happened — so you can always see whether the
rewrite is the thing that broke a query.

Design note worth quoting: it costs one small LLM call, is only made when history exists,
and **falls back to the raw question on any failure** — a broken rewrite can never take the
chat down.

**Q34. What query rewriting does *not* exist here, and what would it fix?**

Rewriting a *first* question. Nothing normalises "how many days can I roll over" into
"carry-over cap". Most relevantly: **`HARD-04` names no region at all**, so no retriever can
win it — it's excluded from every metric as `ambiguous=True`. The backlog calls the fix
"Region auto-detection from the question". That's a rewriting/classification step, not a
retrieval step, and it is the one honest "we cannot fix this with a better retriever" case
in the project.

**Q35. What is HyDE and when does it beat plain rewriting?**

Hypothetical Document Embeddings: ask the LLM to *write a fake answer* to the question, then
embed that fake answer and search with it instead of the question. It works because a
question and its answer are often far apart in embedding space, while a hypothetical answer
sits near the real one — you're doing answer-to-answer similarity instead of
question-to-answer.

Costs: one LLM call per query (latency + money), and it can hallucinate the query off-target
on niche corpora. Not implemented here. On this corpus it would likely *hurt* — a
hypothetical HR answer invents plausible numbers that could pull toward the wrong region.

---

### A8. Measuring it

**Q36. Define hit-rate@k, recall@k and MRR precisely.**

- **hit-rate@k** — fraction of queries where *at least one* correct document appears in the
  top k. Binary per query. "Did the model get a chance?"
- **recall@k** — fraction of *all* relevant documents that appear in the top k, averaged
  over queries. Identical to hit-rate@k when there is exactly one correct document per query
  — which is this project's case, so reporting both here would be reporting the same number twice.
- **MRR** — mean of `1/rank_of_first_correct` (0 if not found). Rewards climbing:
  rank 3 → 1 takes 0.33 → 1.00 even though hit-rate@3 never moves.

**Q37. How does the code compute them?**

`policy_rag/evaluation/retrieval.py`:

```python
NOT_FOUND = 999
rank  = first_correct_rank(retrieved, expected_source)   # 1-based, else 999
hit1  = rank <= 1
hit3  = rank <= 3
rr    = round(1 / rank, 4) if rank < NOT_FOUND else 0.0
```

and `_score_rows` averages over `scorable = [r for r in rows if r["expected_source"] and not r["ambiguous"]]`.

**Q38. Why are ambiguous questions excluded from the metrics rather than scored 0?**

Because `HARD-04` has no single correct document — scoring it would invent a number. Counting
it as a miss would understate the retriever; counting any result as a hit would overstate it.
The honest move is to exclude it *and report that you excluded it*, which the report does in
its "WHAT HYBRID RETRIEVAL DOES NOT FIX" section. Silently dropping it would be fraud.

**Q39. Why does this project report `core` and `hard` separately instead of one average?**

Because a single average hides the result. Aggregate MRR is 0.894 → 0.894: "no change".
Split, the story is +0.063 on the set users actually query and −0.167 on a 3-question stress
set. The average is arithmetically true and analytically useless.

**Q40. Which metric should you headline for a retrieval change?**

- If your baseline misses documents entirely → **hit-rate@k**. That's the ceiling on everything.
- If your baseline finds them but ranks them badly → **MRR** (or hit-rate@1).
- Always report **n**. At n=3, one question is 0.33 of your hit rate.

**Q41. ⚠️ The trap in your Week 4 deliverable — read this one twice.**

The assignment says *"buy back hit-rate@3 with exactly one change."* **Your vector-only
baseline is already hit-rate@3 = 1.000 on all 11 scorable questions.** There is nothing to
buy back. Hybrid moved hit-rate@3 by exactly 0.000 on every set.

You have three legitimate responses, and doing nothing is not one of them:
1. **Headline hit-rate@1 / MRR instead**, and state explicitly that hit-rate@3 was saturated
   at baseline so it had no headroom. Defensible and honest.
2. **Add genuinely failing questions to `HARD_QUERIES`** — paraphrase-only queries, misspelled
   region codes, questions where the answer is in a section the biencoder never surfaces —
   so hit-rate@3 has room to move. Write them *before* you look at the results.
3. **Lower k.** Report hit-rate@1 as your "@k", since that's where your headroom lives.

Option 1 + 2 together is the strongest submission.

---

## Part B — Week 5 · Module 3: Error analysis

### B1. Sampling

**Q42. Random vs curated sampling — why does it matter?**

A curated set contains the failures you already knew about. Reading it teaches you nothing
new; it only re-confirms your priors. A random sample surfaces failure modes you never
guessed, which is the entire reason the week exists. Curation also biases *frequency*: if
you hand-pick 20 traces, your taxonomy's counts are a picture of your own attention, not of
the system.

**Q43. ⚠️ Is this project's 20-trace set a fair sample? Answer honestly.**

**No, and you must say so.** `ANSWER_QUALITY_SUITE = CORE_QUERIES + REFUSAL_QUERIES +
EDGE_QUERIES` = 8 + 4 + 8 = exactly 20 traces. That is a **curated golden set**, hand-written
to probe known-hard cases. It is excellent for regression testing and it is *not* a random
sample of real traffic.

Mentor check #1 is literally *"Did they read a fair sample, not just the good examples?"* —
so fix it. The trace log already separates them:

```python
default_store.read(source="chat")        # real traffic
default_store.read(source="evaluation")  # the golden suite
```

Draw ~20 with `random.sample` from `source="chat"` and read those. Keep the golden run as
your *regression* set; present the random draw as your *error-analysis* set. Two sets, two
jobs, both stated.

**Q44. What's the practical minimum sample size and why 20?**

Twenty is a working compromise: enough that a failure mode occurring in ~15% of traffic will
almost certainly appear at least once, and small enough that you can genuinely read every one
by hand in an hour. It is not enough to *rank* two modes that differ by one occurrence —
which is why severity, not just frequency, breaks ties.

---

### B2. Open coding

**Q45. What is open coding, and what's the strict rule?**

Read one failure, write **one honest sentence** about what went wrong, in your own words —
*before* you have decided what the categories are. Categories emerge from the notes; notes
must never be squeezed into pre-existing categories. The moment you start with a category
list, you stop discovering and start filing.

**Q46. Does this project do open coding? Be precise.**

It *imitates* the shape correctly and skips the human part. `taxonomy.classify()` returns
`{"label", "observation", "retrieval_ok", "top_sources"}`, and the module docstring
explicitly states the order: *"Observe. Read the trace and write one honest sentence about
what happened (`classify` produces the observation before the label)."* Example generated
observation:

> "addendum_UK.txt missing from the top 3 (rank 1 was addendum_EMEA.txt), so the answer was
> delivered confidently from the wrong region's policy."

But that sentence is written by a template from fields the code already knows. It cannot
notice anything the taxonomy doesn't already have a branch for — which is precisely the
thing open coding exists to catch.

Mentor check #2 is *"Is there an honest note per failure, written before grouping them?"*
**Add a human note column.** Read the 20 traces yourself, write your own sentence per
failure in a scratch file, and only then compare against the machine labels. The
disagreements are the most valuable output of your week.

**Q47. What should a good open-coded note contain?**

What the user asked, what came back, and *what specifically is wrong* — not a category.

- Bad: "retrieval issue"
- Bad: "the model hallucinated"
- Good: "Asked about 5-year sabbatical; top 3 were all UK chunks, and UK's threshold is 10
  years, so it answered with the UK rule. The number '5' never matched anything."

The good one names the mechanism. You can derive a category from it later; you cannot derive
a mechanism from a category.

---

### B3. Taxonomy and ranking

**Q48. What is an error taxonomy and what makes a good category name?**

A small closed set of named failure modes covering your observed failures. Good names are
what a stranger could apply to a new trace without asking you: *"Wrong region retrieved"*,
*"Right doc, misread cap table"*, *"Refused despite having the answer"*. Bad names are
*"Model issues"*, *"Edge cases"*, *"Misc"* — a category everything fits into sorts nothing.

Rule of thumb: 3–7 categories. Fewer and you're not distinguishing; more and you're
describing individual traces.

**Q49. This project's taxonomy and severities — recite them.**

`LABEL_META` in `policy_rag/observability/taxonomy.py`:

| Label | Severity | Meaning |
|---|---|---|
| `RETRIEVAL_FAILURE` | 5 | wrong region / no doc |
| `GENERATION_FAILURE` | 4 | right doc, wrong answer |
| `PIPELINE_ERROR` | 4 | request failed |
| `UNKNOWN` | 3 | needs manual inspection |
| `CORRECT` | 0 | not a bug |
| `CORRECT_REFUSAL` | 0 | not a bug |
| `UNLABELED` | 0 | live traffic, no gold answer |

**Q50. Justify severity 5 for retrieval vs 4 for generation.**

Calibrated to the domain, as the docstring says: *"a confidently wrong answer about someone's
leave entitlement is worse than an awkward sentence."* A retrieval failure produces a fluent,
correctly-cited answer from the **wrong region's policy** — the user has no signal that
anything went wrong, and the citation actively increases their trust. A generation failure
usually leaves a tell: hedging, a refusal, a visibly odd number. Undetectable wrongness beats
detectable wrongness on severity.

**Q51. Why rank by frequency × severity rather than either alone?**

- Frequency alone → you spend the sprint on a cosmetic issue that happens constantly.
- Severity alone → you spend it on a catastrophic issue that happens once a year.

The product approximates total harm. In code:

```python
rows.append({..., "score": count * meta["severity"]})
rows.sort(key=lambda r: (-r["score"], -r["count"], r["label"]))
```

Note the deterministic tie-break (`-count`, then `label`) — the ranking is reproducible run
to run, which matters when you're diffing two reports.

**Q52. What are the limits of a multiplicative score?**

Severity is an ordinal scale being used as if it were a ratio scale — "5" is not literally
1.25× as bad as "4". The product is a *heuristic for ordering*, not a measurement. Two rows
scoring 20 and 18 are not meaningfully different; a row at 25 vs one at 4 is. Use it to pick
the top item, not to rank the tail.

---

### B4. Choosing the fix and predicting

**Q53. Why exactly one change?**

Attribution. Change hybrid + prompt + top-k together, watch MRR move +0.05, and you have
learned nothing — you can't tell which one helped, whether two helped and one hurt, or
whether it was noise. This project's own history is the proof: hybrid alone produced +0.125
on one set and −0.333 on another. Bundled with a prompt change, that signal would have been
invisible.

**Q54. What is a prediction card and why write it before the change?**

A written statement, made *before* you run anything, of: the problem, its root cause, the one
change, what metric should move and by roughly how much, and **what it will not fix**. It
converts your work from post-hoc storytelling into a falsifiable experiment. Without it, any
result gets rationalised as a success.

**Q55. Reproduce this project's prediction card structure.**

`taxonomy.REMEDIATION` + `prediction_card()`. Fields: `cause`, `change`, `prediction`,
`will_not_fix`. For the top-ranked problem:

> **Problem:** Retrieval failure — *n*/20 traces, severity 5/5
> **Root cause:** Queries without a region filter let all six addenda compete in vector space.
> The highest cosine similarity wins regardless of which region the user is in.
> **One change:** Hybrid retrieval — fuse BM25 with the vector retriever using RRF. Region
> codes and section numbers are exact-match targets for BM25.
> **Prediction:** hit-rate@3 and MRR rise for region-explicit and exact-term queries.
> Correct refusals unaffected.
> **Will not fix:** Fully ambiguous queries naming no region, and generation failures where
> the right document was already retrieved.

`prediction_card()` picks `next((row for row in taxonomy if row["severity"] > 0), None)` —
the highest-scoring row that is actually a bug.

**Q56. Grade that prediction against what actually happened.**

Partially wrong, and that is a *good* thing to present. It predicted "hit-rate@3 and MRR rise
for region-explicit **and exact-term** queries."

- Region-explicit: correct on MRR (0.938 → 1.000), wrong on hit-rate@3 (already 1.000, no
  headroom — the prediction named a saturated metric).
- Exact-term: **wrong in direction** — MRR fell 0.778 → 0.611.

That is exactly why you write the prediction first. Say this out loud in your review: *"I
predicted X, I measured Y, here's the mechanism I'd missed (RRF discards the biencoder's
confidence — see Q22)."* A mentor values a falsified prediction with a diagnosis far more
than an unfalsifiable "it improved".

**Q57. Benchmarks (MMLU, HumanEval) vs your app's evals — what's the relationship?**

MMLU and HumanEval measure *general model capability* on public, static, contamination-prone
tasks. They tell you roughly which model to start with. They tell you nothing about whether
your chunker splits eligibility tables, whether your embedding model can distinguish
`addendum_US` from `addendum_LATAM`, or whether your refusal sentinel fires correctly. Those
are properties of *your pipeline over your corpus*, and only your own eval set measures them.
A model can top every leaderboard and still be useless here if retrieval hands it the wrong
addendum — which is the whole Week 4 point.

---

## Part C — Codebase gotchas worth understanding

**Q58. How is a refusal detected, and what is fragile about it?**

```python
"is_refusal": config.REFUSAL_SENTINEL in answer_text_value
```

A substring check against a constant that must stay **byte-identical** to the sentence
embedded in `QA_PROMPT_TEMPLATE` (the config comment says so explicitly). If the LLM
paraphrases even slightly — different apostrophe, dropped period — the refusal is missed,
the trace is labelled as an answer, and your taxonomy silently miscounts. Every metric
downstream inherits that error.

**Q59. What breaks if you re-ingest and forget one call?**

`_cached_query_engine` is `@functools.lru_cache(maxsize=32)` keyed on
`(region, top_k, hybrid)`, holding retrievers bound to the *old* docstore and BM25 node list.
`reset_engine_cache()` must be called after re-ingestion, or a long-running server keeps
answering from a stale index while `chroma_db/` on disk says otherwise. Silent, and it will
poison a whole eval run.

**Q60. Why does the eval suite sleep 13 seconds between questions?**

`config.EVAL_PAUSE_SECONDS = 13`. Gemini's free tier allows 5 requests/minute. An
unthrottled 20-question run turns into a page of 429s, and — the key line — *"scores the rate
limiter instead of the assistant."* A run that trips rate limits produces `PIPELINE_ERROR`
traces that inflate your taxonomy with an infrastructure problem dressed as a quality problem.

**Q61. Why does `answer()` still write a trace when the request fails?**

The `except` block records `error = f"{type(exc).__name__}: {exc}"` into the envelope rather
than swallowing it, and `classify()` turns that into `PIPELINE_ERROR` at severity 4. Failures
that leave no trace are invisible to error analysis, and invisible failures are the ones that
persist. Note the retry is exponential (`retry_delay * (2 ** attempt)`) because rate limits
are enforced over a window — a linear retry lands inside the same window.

**Q62. What happens with no `GEMINI_API_KEY`?**

`configure_settings()` falls back to `MockLLM`, prints a warning, and `active_llm_name()`
returns `"MockLLM (no GEMINI_API_KEY)"` — recorded on every trace. That's deliberate: it
keeps retrieval-only work (`ingest`, `eval retrieval`, `eval chunking`) runnable without a
key, since none of those call the LLM. It's still the top backlog item, because the fallback
is *labelled* but not *loud* — you can run `eval quality` against a mock and get a report
full of meaningless answers.

---

## Part D — Gap checklist before the mentor review

Against the mentor's four checks per module:

| # | Mentor check | Status | Action |
|---|---|---|---|
| W4-1 | Can you show, for a specific failure, which of the two kinds it is — with evidence? | **Strong** | Walk through `taxonomy.classify`'s branch + a real trace's `retrieved_chunks`. |
| W4-2 | One change, not five? | **Strong** | Hybrid only. `num_queries=1` even keeps the LLM out of the fusion. |
| W4-3 | Before-and-after number? | **Strong** | `docs/evaluation-results.md` §9, both directions reported. |
| W4-4 | hit-rate@3 bought back? | **⚠️ Fails as stated** | Baseline is already 1.000. Headline hit-rate@1 / MRR **and say why**, plus add harder queries (Q41). |
| W5-1 | Fair sample, not cherry-picked? | **⚠️ Curated** | Random-sample ~20 from `source="chat"`. Keep the golden 20 as the regression set (Q43). |
| W5-2 | Honest note per failure, written before grouping? | **⚠️ Machine-generated** | Hand-write your own note per failure first, then diff against `observation` (Q46). |
| W5-3 | Category names a stranger understands? | **Strong** | `LABEL_META[*]["display"]` are plain-English. |
| W5-4 | Ranked, with a chosen target? | **Strong** | `build_taxonomy` (freq × severity) + `prediction_card`. |

Two more worth doing if you have time:
- **Ship the cross-encoder reranker** (backlog, Medium). It's the named next step whenever
  the taxonomy ranks generation failures first, and it gives you a *second* one-change
  before/after — this time on a metric with headroom.
- **Grade your last prediction in writing** (Q56). Predicted vs measured vs mechanism.

### Commands to regenerate the evidence

```
policy-rag eval retrieval -v      # hit-rate@1/@3, MRR, vector vs hybrid, per question
policy-rag eval quality           # 20 traces, taxonomy, prediction card (writes reports/answer-quality.md)
policy-rag eval quality --from-traces   # rebuild the report with no LLM calls
policy-rag traces --limit 20 --source chat --json
policy-rag chat "..." --json      # one full trace envelope
```