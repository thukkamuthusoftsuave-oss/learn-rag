# Retrieval Debugging, Hybrid Search & Error Analysis
### A complete learning guide, using the HR-207 RAG project as the running example throughout

---

> **How to use this guide**  
> Every concept here is tied to a real line of code in this project.  
> You can reproduce every example with `policy-rag chat ...`.  
> Read each section in order — later sections build on earlier ones.

---

## Table of Contents

1. [The Two Kinds of Wrong](#1-the-two-kinds-of-wrong)
2. [What Is a Trace?](#2-what-is-a-trace)
3. [The Inspection View](#3-the-inspection-view)
4. [Keyword Search (BM25)](#4-keyword-search-bm25)
5. [Hybrid Search (RRF Fusion)](#5-hybrid-search-rrf-fusion)
6. [Reranking (Cross-Encoder)](#6-reranking-cross-encoder)
7. [MMR — Maximum Marginal Relevance](#7-mmr--maximum-marginal-relevance)
8. [Query Rewriting and HyDE](#8-query-rewriting-and-hyde)
9. [Measuring It: hit-rate@k, recall@k, MRR](#9-measuring-it-hit-ratek-recallk-mrr)
10. [Error Analysis: Reading Traces Professionally](#10-error-analysis-reading-traces-professionally)
11. [Open Coding: Writing One Honest Sentence Per Failure](#11-open-coding-writing-one-honest-sentence-per-failure)
12. [Error Taxonomy and Ranking](#12-error-taxonomy-and-ranking)
13. [Choosing the One Fix](#13-choosing-the-one-fix)
14. [Reference: What the Curriculum Wants You to Demonstrate](#14-reference-what-the-curriculum-wants-you-to-demonstrate)

---

## 1. The Two Kinds of Wrong

This is the most important idea in this document. Everything else flows from it.

### The Two Categories

| Category | What happened | Example in HR-207 | Fix |
|---|---|---|---|
| **Retrieval failure** | The app fetched the wrong document (or no document at all) | Query "What is the carry-over cap for a probationary employee?" without --region US retrieves LATAM's Section 4.2 at rank 1 | Fix retrieval: add metadata filter, hybrid search, rerank |
| **Generation failure** | The app fetched the **right** document and still gave a wrong answer | Query returns US Section 4.2 (correct) but the model confuses "probationary" (5 days) with "regular" (10 days) | Fix the prompt, add more context, or do fine-tuning |

### Why This Distinction Matters So Much

**The wrong diagnosis costs real money and time.**

If you have a retrieval failure and you switch to a smarter model (GPT-4o instead of Gemini Flash), you are feeding the new model the *same wrong document*. It will confidently hallucinate a better-sounding wrong answer. You paid 20x more and fixed nothing.

If you have a generation failure and you add hybrid search, the retriever now returns the right document even faster — but the model still reads it and makes the same reasoning error. Also fixed nothing.

### How to Tell Them Apart — The Decision Test

Look at the PARAMETERS block that the `policy-rag chat` command already emits:

```
retrieved_chunks (4):
  [1] score=0.3596 source=addendum_US.txt node=5e3ef949-...
  [2] score=0.3586 source=addendum_US.txt node=13b36478-...
  [3] score=0.3537 source=addendum_US.txt node=0b75519b-...
  [4] score=0.3506 source=addendum_US.txt node=81fc7c63-...
```

**Ask: Is the correct source file present in the retrieved chunks?**

- **Yes, but wrong answer -> Generation failure.** The right document is there. The model misread it.
- **No, or it appears at rank 4+ -> Retrieval failure.** The right document was not in the context window at all, or was buried below the threshold.

### Your HR-207 Example

Run this (no region filter):

```powershell
policy-rag chat "What is the carry-over cap for a senior employee?"
```

The output shows `addendum_LATAM.txt` or `addendum_EMEA.txt` at rank 1, not `addendum_US.txt`. That is a **retrieval failure** — the question is ambiguous (no region specified) and the wrong region wins the vector similarity race.

Run this (with region filter):

```powershell
policy-rag chat "What is the carry-over cap for a senior employee?" --region US
```

Now `addendum_US.txt` is at rank 1 and the answer is correct. The metadata pre-filter *fixed a retrieval failure* without touching the LLM at all.

---

## 2. What Is a Trace?

A **trace** is the complete, replayable record of a single request. It contains enough information that someone who was not present could reconstruct exactly what happened.

### Minimum Viable Trace Fields

```
query:            "What is the selfcare policy?"
region_filter:    US
top_k:            5
timestamp:        2026-08-14T09:47:06Z

retrieved_chunks:
  [1] score=0.3596 source=addendum_US.txt  node_id=5e3ef949-...
  [2] score=0.3586 source=addendum_US.txt  node_id=13b36478-...
  [3] score=0.3537 source=addendum_US.txt  node_id=0b75519b-...
  [4] score=0.3506 source=addendum_US.txt  node_id=81fc7c63-...

answer:           "I'm sorry, I cannot answer that question based on the provided documents."
is_refusal:       True

tokens:           prompt=876  completion=16  total=892  (estimated-tiktoken)
latency_ms:       4534
llm_model:        models/gemini-flash-latest
embed_model:      BAAI/bge-small-en-v1.5
```

This is **exactly what --json gives you already.** You saw this in the terminal output you ran:

```powershell
policy-rag chat "What is selfcare?" --region US
```

The refusal happened because "selfcare" does not exist in any of the 6 addendum files. The retriever fetched 4 chunks (all from addendum_US.txt, which is correct given --region US) but the content was policy clauses, not anything about self-care. The LLM correctly refused. This is a **correct refusal** — not a bug, not a failure.

### Why Traces Need All These Fields

| Field | Why It Cannot Be Missing |
|---|---|
| `retrieved_chunks` with scores and sources | Without this you cannot tell if it's a retrieval or generation failure |
| `is_refusal` flag | Lets you programmatically separate real answers from refusals in batch analysis |
| `timestamp` | Lets you correlate with index changes, model version changes |
| `embed_model` + `llm_model` | A trace is useless if you don't know which models produced it |
| `tokens` | Lets you spot cost anomalies — a 20,000-token prompt means context stuffing |

### Why Not Just Log the Final Answer?

Because the answer alone tells you nothing about *why*. If the answer is wrong, you cannot tell whether to fix retrieval or generation without the chunks. This is equivalent to a developer removing all logging from a server and then wondering why it crashed.

---

## 3. The Inspection View

An inspection view is a side-by-side layout that shows: **Question | Retrieved Chunks | Final Answer**. The goal is to let a human spot retrieval failures in 5 seconds, not 5 minutes.

### The Simplest Possible Inspection View (Already In This Project)

The `--json` flag gives you a machine-readable trace. Pipe it to a file and read it as a table:

```powershell
policy-rag chat "Who is eligible for sabbatical?" --json > trace_001.json
```

For batch inspection, the project has policy_rag/evaluation/smoke.py which runs 3 scenarios and prints question + answer + refusal status. This is a minimal but functional inspection view.

### What a Proper Inspection View Adds

For a real batch (20+ queries), log each trace to a JSONL file:

```json
{"q_id": 1, "query": "...", "retrieved": [...], "answer": "...", "is_refusal": false}
{"q_id": 2, "query": "...", "retrieved": [...], "answer": "...", "is_refusal": true}
```

Then read it row-by-row and label each one:
- `retrieval_ok: true/false` — Was the correct source in the retrieved chunks?
- `answer_ok: true/false` — Was the final answer correct?
- `failure_type: retrieval | generation | correct | correct_refusal`

**This labeling is the most important manual step in the whole exercise.** It cannot be automated because "is this the correct source?" requires knowing the ground truth.

### Why Not Use Automated Metrics Only?

Automated metrics (hit-rate@k, MRR) tell you *aggregate* numbers. They cannot tell you *why* a specific query failed. A query can hit at rank 1 and still get a wrong answer. The inspection view is what bridges aggregate numbers to individual diagnoses.

---

## 4. Keyword Search (BM25)

### What Is BM25?

BM25 (Best Match 25) is a scoring formula that ranks documents by **exact word overlap** between the query and document, adjusted for document length and term frequency. It is the engine behind most traditional search systems (Elasticsearch, Solr, Lucene).

Think of it as: *how many of the exact words in your query appear in this document, accounting for the fact that rare words matter more than common ones.*

### How It Differs from Vector (Semantic) Search

| Feature | BM25 (Keyword) | Vector (Semantic) |
|---|---|---|
| Finds | Exact word matches | Conceptual meaning |
| Good for | Codes, IDs, names, acronyms | Paraphrases, synonyms, intent |
| Fails when | Query uses a synonym the doc doesn't have | Query uses exact jargon the model hasn't seen |
| Example hit | "ERR-4032", "Section 4.7", "HR-207" | "Am I allowed time off?" matches "vacation eligibility" |
| Example miss | "time off" if doc says "vacation" | "HR-207" if the model treats it as a generic label |

### Why BM25 Matters in HR-207

Your current policy_rag/evaluation/chunking.py uses TF-IDF + cosine similarity for the offline evaluation. TF-IDF is a simplified version of BM25. The reason structure-aware chunking helps so much (8/8 vs 1/8) is that the section header text `HR-207 Section 4.2` appears **inside** the chunk text, which is pure keyword match gold.

But consider this real failure case from the terminal output you saw:

```powershell
policy-rag chat "What is selfcare?" --region US
# Answer: "I'm sorry, I cannot answer..."
# retrieved_chunks: all from addendum_US.txt, score approx 0.35
```

The vector embedder saw "selfcare" and found the closest conceptual neighbors — which happened to be wellness-adjacent policy sections. BM25 would have found zero exact matches for "selfcare" in the corpus and returned an empty result immediately, making the refusal cleaner and cheaper.

### The Exact Term Problem

Imagine a user asks: `"What does Section 4.7 say about part-time employees?"`

- **BM25** finds `Section 4.7` instantly — it is a literal string match.
- **Vector Search** might retrieve Section 4.1 or 4.2 because "part-time employees" is conceptually close to "eligibility" sections. It might miss the 4.7 literal target.

### Why Not Use BM25 Alone?

BM25 breaks entirely on paraphrases. If a user asks "Am I allowed to carry over leave as a new hire?", BM25 needs the words "carry", "over", "leave", "new", "hire" to all appear in the document. But the document says:

```
Probationary (< 6 months) | 5 days
```

Zero overlap. BM25 returns nothing. Vector search would correctly link "new hire" -> "probationary" -> "5 days cap".

---

## 5. Hybrid Search (RRF Fusion)

### The Core Idea

Run BM25 and vector search independently, get two ranked lists, and merge them with a formula that rewards results that appear high in *both* lists. This is **Reciprocal Rank Fusion (RRF)**.

### RRF Formula

For each document `d`, its RRF score is:

```
RRF(d) = sum of  1 / (k + rank_in_list_i)  across all retriever lists

Where k = 60 (constant that dampens the effect of very high ranks)
      rank_in_list_i = position in the i-th ranked list (1-indexed)
```

**Example:** A document appears at rank 1 in vector search and rank 3 in BM25:

```
RRF = 1/(60+1) + 1/(60+3) = 0.01639 + 0.01587 = 0.03226
```

A document at rank 1 in vector but rank 15 in BM25:

```
RRF = 1/(60+1) + 1/(60+15) = 0.01639 + 0.01333 = 0.02972
```

The document that ranked well in *both* wins.

### Applied to HR-207: The Part-Time Scenario

**Query:** "I am a part-time employee working 20 hours a week — what are my carry-over rights?"

| Rank | Vector Only | BM25 Only | Hybrid (RRF) |
|---|---|---|---|
| 1 | US Section 4.1 (eligibility) | US Section 4.7 (part-time rule) | **US Section 4.7** correct |
| 2 | US Section 4.2 (cap table) | US Section 4.2 (cap table) | US Section 4.2 correct |
| 3 | US Section 4.4 (expiry) | US Section 4.1 (eligibility) | US Section 4.1 correct |

Vector alone misses Section 4.7 because "part-time" is semantically close to many sections. BM25 nails Section 4.7 because the literal phrase "20 hours per week" is in that section of addendum_US.txt: *"Part-time employees working fewer than 40 hours per week..."*. Hybrid fuses them and the right document rises.

### Why Not Just Weight the Vector Score Higher?

Because "higher weight" is a tuning guess. Tuning requires data. RRF is **parameter-light** — the constant k=60 is nearly universal and you do not need training data to make it work. For a small corpus like 6 addenda with ~74 nodes, RRF works immediately.

### Why Not Use a Learned Fusion?

Learned fusion (training a model to combine scores) requires labeled query-document relevance pairs. You would need hundreds of labeled examples. For an HR policy corpus with 8 known-answer questions, you don't have that data. RRF gives you most of the benefit for free.

### How to Add Hybrid Search to This Project

Currently policy_rag/retrieval/engine.py uses only vector search. Adding BM25 requires:

```python
# pip install llama-index-retrievers-bm25

from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever

bm25_retriever = BM25Retriever.from_defaults(nodes=all_nodes, similarity_top_k=top_k)
vector_retriever = index.as_retriever(similarity_top_k=top_k, filters=filters)

hybrid_retriever = QueryFusionRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    similarity_top_k=top_k,
    mode="reciprocal_rerank",   # RRF
)
```

The AutoMergingRetriever wraps this hybrid retriever the same way it currently wraps the vector-only retriever.

---

## 6. Reranking (Cross-Encoder)

### The Problem Reranking Solves

Vector search produces a **biencoder** similarity: it embeds the query once and the document once, independently, then compares the two vectors. This is fast but coarse. The query embedding and document embedding never "look at each other" — they are compared post-hoc.

A **cross-encoder** reads the query *and* the document together in a single forward pass. It can understand the relationship between them at a much deeper level: does this document actually answer *this specific question*?

### Biencoder vs Cross-Encoder

| | Biencoder (vector search) | Cross-Encoder (reranker) |
|---|---|---|
| How it works | Embed query -> Embed doc -> cosine distance | Feed [query + doc] together -> single relevance score |
| Speed | Fast (pre-computed doc embeddings) | Slow (must process every candidate pair) |
| Accuracy | Good | Much better |
| When to use | First-pass retrieval (candidate generation) | Second-pass reranking (rescoring the top-K) |

### The Two-Stage Pattern

```
Query -> Vector Search -> Top-20 candidates -> Reranker -> Top-5 for LLM
                                                  |
                              Cross-encoder reads each (query, candidate) pair
                              and scores them for true relevance
```

You keep the fast vector search to get candidates. You only run the expensive cross-encoder on the small set (20 candidates). The final top-5 given to the LLM is much higher quality.

### Applied to HR-207

**Query:** "What defines continuous service in the US policy?"

Vector search might return these 5 chunks:

```
[1] score=0.71  US Section 4.1 Eligibility    <- correct
[2] score=0.69  NA Section 4.1 Eligibility    <- WRONG REGION
[3] score=0.68  US Section 4.2 Carry-over Cap
[4] score=0.65  UK Section 4.1 Eligibility    <- wrong region
[5] score=0.64  EMEA Section 4.1 Eligibility  <- wrong region
```

The cross-encoder reads ("What defines continuous service in the US policy?", "Employees are eligible for carry-over based on continuous service. Continuous service means 40 hours per week for 52 weeks. [US]") and produces a high score. It reads the NA and UK chunks and gives them lower scores because the US-specific definition does not match.

After reranking:

```
[1] score=0.94  US Section 4.1   <- correct
[2] score=0.72  US Section 4.2
[3] score=0.41  NA Section 4.1
```

### Popular Rerankers

| Model | Type | Why and When |
|---|---|---|
| **Cohere Rerank** | API (cloud) | Easiest to add, handles long documents well, 1 API call |
| **BAAI/bge-reranker-base** | Local HuggingFace | Matches BGE embedding style, free, runs offline — best fit for this project |
| **cross-encoder/ms-marco-MiniLM-L-6-v2** | Local HuggingFace | Very fast, good for short passages |

**For this project, bge-reranker-base is the most natural choice** because you are already using BAAI/bge-small-en-v1.5 for embeddings. Using matching BGE family models is a recommended practice.

### Why Not Rerank Everything?

If you have 10,000 documents and run the cross-encoder on all of them, it would take minutes per query. Rerankers are only practical on a small candidate set (typically top-20 to top-50). The first-stage vector search narrows the field cheaply, the reranker refines the shortlist accurately.

### Adding a Reranker to This Project

```python
# pip install llama-index-postprocessor-flag-embedding-reranker

from llama_index.postprocessor.flag_embedding_reranker import FlagEmbeddingReranker

reranker = FlagEmbeddingReranker(model="BAAI/bge-reranker-base", top_n=5)

query_engine = RetrieverQueryEngine.from_args(
    retriever=retriever,          # same AutoMergingRetriever
    node_postprocessors=[reranker],
    text_qa_template=PromptTemplate(QA_PROMPT_TEMPLATE),
)
```

The reranker is a node_postprocessor that runs after retrieval, before generation.

---

## 7. MMR — Maximum Marginal Relevance

### The Problem

Your retriever returns Top-5 chunks. But what if 4 of those 5 chunks are essentially duplicates — all slightly different fragments of Section 4.2 Carry-over Cap from addendum_US.txt? You've wasted 80% of your context window on redundant information.

This is what happens in the example output you saw:

```
retrieved_chunks (4):
  [1] score=0.3596 source=addendum_US.txt node=5e3ef949-...
  [2] score=0.3586 source=addendum_US.txt node=13b36478-...
  [3] score=0.3537 source=addendum_US.txt node=0b75519b-...
  [4] score=0.3506 source=addendum_US.txt node=81fc7c63-...
```

All 4 nodes are from the same file, with very similar scores. They are likely adjacent child chunks of the same parent. The AutoMergingRetriever already partially solves this (by merging them into one parent), but MMR is a more explicit diversity mechanism.

### How MMR Works

At each selection step, MMR chooses the next chunk that maximizes:

```
MMR(d) = lambda * Relevance(query, d)  -  (1-lambda) * max Similarity(d, already_selected)
```

- `lambda = 1` -> pure relevance (same as regular retrieval)
- `lambda = 0` -> pure diversity (pick maximally different chunks)
- `lambda approx 0.7` -> a useful balance

**In plain English:** Pick the next document that is relevant to the query *and* different from what you already picked.

### Applied to HR-207

Without MMR, Top-5 for "What is the carry-over cap?" might give you:

- Section 4.2 paragraph 1
- Section 4.2 paragraph 2
- Section 4.2 paragraph 3
- Section 4.2 table row block
- Section 4.2 final sentence

With MMR (lambda=0.7):

- Section 4.2 (most relevant)
- Section 4.1 Eligibility (relevant + adds new prerequisite info)
- Section 4.4 Expiry (relevant + different aspect of carry-over)
- Section 4.7 Part-time rule (tangentially relevant + diverse)
- Section 4.5 Payout (adds termination context)

This is exactly the **"precision/completeness tension"** documented in docs/evaluation-results.md section 7 — retrieving Section 4.2 without 4.1 causes the part-time eligibility bug. MMR naturally pulls in the neighboring sections.

### Why Not Just Increase Top-K?

If you retrieve Top-10 instead of Top-5, you get more content but also more noise and a 2x longer prompt. MMR achieves diversity *within* the same Top-K budget.

---

## 8. Query Rewriting and HyDE

### Problem: Users Write Bad Queries

Users don't search like a document. A user might type:

```
"i been here 3 years part time whats my days"
```

The underlying information need is:

```
"What is the carry-over cap for a part-time employee with more than 2 years of service in the US?"
```

The first query will retrieve very different chunks from the second, even though they mean the same thing.

### Query Rewriting

**Query Rewriting** uses an LLM to transform the user's messy query into a cleaner, more retrieval-friendly form before embedding it.

```python
REWRITE_PROMPT = """
Rewrite the following user question into a precise search query for an HR policy document.
Remove colloquial language. Use formal HR terminology.
User question: {query}
Search query:
"""
```

For this project, you would add this as a pre-processing step in policy_rag/retrieval/engine.py before calling engine.query().

**Why LLM for rewriting, not a rule system?**
Rules cannot handle the infinite variety of casual human phrasing. An LLM can. This is one place where the LLM is used *before* retrieval, not after.

**Why Not Always Rewrite?**
Query rewriting adds one extra LLM call per query (latency + cost). For technical queries with explicit terms like "Section 4.7" or "HR-207", rewriting may actually hurt by paraphrasing away the exact keyword BM25 would have matched. The decision depends on your user population.

### HyDE (Hypothetical Document Embeddings)

**HyDE** is a clever trick: instead of embedding the query, ask the LLM to *generate a hypothetical answer document* and embed that.

```
Step 1: Query = "What is the carry-over cap for a probationary employee in US?"

Step 2: LLM generates a hypothetical answer:
"For probationary employees in the US (those with less than 6 months of service),
the carry-over cap under HR-207 is 5 days per calendar year..."

Step 3: Embed the hypothetical answer, not the query.

Step 4: Use this embedding to search the vector store.
```

**Why This Works:**
The hypothetical answer is written in the *same style and vocabulary* as the actual policy documents. Its embedding is much closer to the real document embedding than a short user query's embedding would be.

**When HyDE Helps:**
- When user queries are short and under-specified
- When the vocabulary gap between user language and document language is large

**When HyDE Hurts:**
- If the LLM confidently hallucinates a wrong hypothetical (invents a "30 day cap" when the real cap is 5 days), the embedding will pull toward the wrong documents
- Adds latency (one extra LLM call before retrieval)

**Applied to HR-207:** HyDE would help for vague questions like "selfcare policy". The LLM would generate a hypothetical about wellness and work-life balance. The embedding would still find no match in the HR-207 corpus (since it is a leave policy corpus, not wellness), and the refusal would be triggered — but more accurately.

---

## 9. Measuring It: hit-rate@k, recall@k, MRR

**This is where "it feels better" becomes "it is 17% better."** Numbers are the currency of this work. Without them, your improvement claim means nothing.

### hit-rate@k (HR@k)

**Definition:** The fraction of queries where the correct document appears in the top-k retrieved results.

```
hit-rate@3 = (number of queries where correct doc is in top-3) / (total queries)
```

**Your existing policy_rag/evaluation/chunking.py already calculates this for k=5.** The table in docs/evaluation-results.md is a hit-rate@5 table:

| Chunker | hit-rate@5 (expanded corpus) |
|---|---|
| Naive 4-line split | 1/8 = 0.125 |
| Structure-aware | 8/8 = 1.000 |

That is your before-and-after number for chunking. The same format is what the retrieval benchmark reports for hybrid search or reranking.

### How to Calculate hit-rate@3 for This Project

For each of the 8 known questions, run retrieval and check if the expected section is in the top-3 chunks. In policy_rag/evaluation/chunking.py, change the top_indices slice:

```python
# Currently slices top 5:
for i in top_indices[:5]:

# Change to top 3 for hit-rate@3:
for i in top_indices[:3]:
```

**Before improvement** (vector-only, no region filter): count how many of the 8 questions have their correct section in the top-3.

**After improvement** (hybrid search or reranker): recount.

Report: **"hit-rate@3 went from 0.50 to 0.88."**

### recall@k

**Definition:** Of all relevant documents that exist in the corpus for a query, what fraction appear in the top-k?

For this project (single correct section per question), recall@k equals hit-rate@k. The distinction matters when a query has multiple correct answers (e.g., "What are the rules for part-time employees?" — Section 4.1 and Section 4.7 are both relevant).

```
recall@3 = (relevant docs found in top-3) / (total relevant docs in corpus)
```

### MRR — Mean Reciprocal Rank

**Definition:** The average of the reciprocal of the rank at which the correct document first appears.

```
MRR = (1/N) * sum of (1/rank_i)
```

Example calculation over 8 queries:

| Query | Rank of correct doc | Reciprocal Rank |
|---|---|---|
| Q1 | 1 | 1.000 |
| Q2 | 1 | 1.000 |
| Q3 | 3 | 0.333 |
| Q4 | 2 | 0.500 |
| Q5 | 1 | 1.000 |
| Q6 | 1 | 1.000 |
| Q7 | 5 | 0.200 |
| Q8 | 1 | 1.000 |

```
MRR = (1/8) * (1 + 1 + 0.333 + 0.5 + 1 + 1 + 0.2 + 1) = (1/8) * 6.033 = 0.754
```

**Why MRR Over hit-rate@k?**

MRR penalizes finding the correct document at rank 5 vs rank 1. A hit-rate@5 of 1.0 is "perfect" even if the correct answer is always at rank 5. MRR = 0.2 (all at rank 5) tells you the retrieval is technically correct but practically bad — the AutoMergingRetriever sends all 5 to the LLM, and a rank-5 correct doc means 4 wrong docs pollute the context first.

### Which Metric to Report for a Retrieval Change?

The curriculum asks for **hit-rate@3** specifically. Report:

```
Before hybrid search: hit-rate@3 = X/8 = 0.XX
After hybrid search:  hit-rate@3 = Y/8 = 0.YY
Change: +ZZ percentage points
```

---

## 10. Error Analysis: Reading Traces Professionally

### The Core Mindset Shift

Retrieval debugging is about fixing a specific thing. Error analysis is about *finding* what to fix. These are completely different skills.

**Debugging mindset:** "I think hybrid search will help — let me measure it."

**Error-analysis mindset:** "I have no assumptions. Let me read 20 answers and write down what I observe."

The danger is **confirmation bias** — you already know hybrid search and reranking are on your mind, so you'll look for retrieval failures. You might completely miss that 30% of failures are actually hallucinations from too much context, or that the citation format is broken. Reading first, categorizing second, is how you avoid this.

### What "A Fair Sample" Means

The curriculum explicitly says: **do not cherry-pick good examples.**

A fair sample for HR-207 would be:

```python
import random

ALL_QUESTIONS = [
    # Known-answer questions (8 from policy_rag/evaluation/chunking.py)
    "What is the carry-over cap for a probationary employee in NA?",
    "What is the carry-over cap for a regular employee with 1 year in EMEA?",
    "What is the carry-over cap for a senior employee in APAC?",
    "When does the HR-207 policy become effective in LATAM?",
    "What defines continuous service in US for the carry-over policy?",
    "Who is eligible for the sabbatical in UK?",
    "What is the max carry-over for a senior with > 2 years of service in US?",
    "Does a regular employee in NA get 15 days carry-over cap?",

    # Adversarial and edge-case questions (add to reach 20)
    "What is the maternity leave policy in EMEA?",       # known correct refusal
    "Who is eligible for sabbatical in LATAM?",          # known correct refusal
    "I worked part-time 20hrs in US for 3 years, how many days?",
    "What happens to my carry-over if I quit tomorrow?",
    "Can my manager deny my carry-over request?",
    "When do carried-over days expire in UK?",
    "What is Section 4.9 about in EMEA?",
    "How do I submit a carry-over request in APAC?",
    "Is a contract worker eligible for carry-over in NA?",
    "What is the sabbatical length in EMEA?",
    "What is the reimbursement limit for home office equipment?",
    "What is selfcare?",
]

# Random sample without replacement — never curate
sample = random.sample(ALL_QUESTIONS, 20)
```

**Why random, not curated?**

Curating means you unconsciously pick questions you expect your system to answer correctly. A random sample gives you the true failure rate. If your system has a 30% failure rate and you cherry-pick, you will observe 5% and believe you've built something much better than you have.

---

## 11. Open Coding: Writing One Honest Sentence Per Failure

**Open coding** is a technique from qualitative research. The rule is: write an observation about what went wrong *before* deciding what category it belongs to. This prevents you from forcing every failure into a pre-existing bucket.

### How to Do It

For each trace in your sample, write:

```
Trace ID: 001
Query: "What is the reimbursement limit for home office equipment?"
Expected: Refusal (topic not in corpus)
Actual: "I'm sorry, I cannot answer that question based on the provided documents."
is_refusal: True

ONE HONEST SENTENCE: Correct refusal — the topic genuinely does not exist
in the corpus and the system correctly identified this.

Label: CORRECT_REFUSAL
```

```
Trace ID: 002
Query: "Who is eligible for sabbatical in LATAM?"
Expected: Refusal (sabbaticals only in EMEA and UK)
Actual: "I'm sorry, I cannot answer that question based on the provided documents."
is_refusal: True

ONE HONEST SENTENCE: Correct refusal — confirmed by policy_rag/corpus/generator.py,
LATAM addendum has no Section 4.3 at all.

Label: CORRECT_REFUSAL
```

```
Trace ID: 003
Query: "What is the carry-over cap for a senior employee?" (no region)
Expected: US Section 4.2 answer OR a clarifying question about region
Actual: Gave LATAM's 15-day cap as the answer.
is_refusal: False

ONE HONEST SENTENCE: Retrieved LATAM's Section 4.2 first because without
a region filter all 6 regions compete in vector space and LATAM happened to
have slightly higher cosine similarity for this query.

Label: RETRIEVAL_FAILURE — Cross-region contamination (missing region context)
```

```
Trace ID: 004
Query: "I worked part-time 20hrs in US for 3 years, how many days?" --region US
Expected: 0 days (Section 4.7 exclusion)
Actual: "0 days — part-time employees below 40 hours are excluded per Section 4.7"
is_refusal: False

ONE HONEST SENTENCE: Correct answer, correctly cites Section 4.7 —
the AutoMergingRetriever merged child chunks from both 4.1 and 4.7
into parent context so the exclusion was visible.

Label: CORRECT
```

**Rule: Write the sentence BEFORE you decide the label.** If you label first, your sentence will just justify the label instead of observing what actually happened.

---

## 12. Error Taxonomy and Ranking

After coding all 20 traces, group your notes into named categories. A good category name should be understandable by someone who has never seen your app.

### Example Taxonomy for HR-207

| Category Name | Count | Severity (1-5) | Score (Count x Severity) | Priority |
|---|---|---|---|---|
| Cross-region contamination | 5 | 5 (wrong law delivered) | 25 | **Fix first** |
| Correct refusals | 6 | 0 (not a bug) | 0 | Ignore |
| Correct answers | 4 | 0 (not a bug) | 0 | Ignore |
| Citation format broken | 3 | 2 (cosmetic) | 6 | Fix third |
| Hallucination on edge case | 1 | 4 (dangerous) | 4 | Fix second |
| Missing prerequisite clause | 1 | 3 (incomplete) | 3 | Fix fourth |

**Cross-region contamination is ranked #1** because: it happens 5 times (highest frequency) and severity is 5/5 (an employee in the US who gets the LATAM rule could make the wrong decision about their vacation — this is a consequential error in an HR system).

### Severity Scale — Calibrate to Your Domain

For an HR policy app:

| Score | Meaning | Example |
|---|---|---|
| 5 | Wrong legal advice, consequential harm | Giving US rules instead of UK rules to a UK employee |
| 4 | Confident hallucination on a real question | Making up a policy section that does not exist |
| 3 | Incomplete answer (missing a prerequisite clause) | Giving the carry-over cap without the eligibility definition |
| 2 | Cosmetic issue | Citation link format is broken but answer is correct |
| 1 | Minor wording oddness | Slightly awkward phrasing but factually correct |

### Why Frequency x Severity?

Because a bug that happens 20 times at severity 1 (score=20) should be prioritized over a bug that happens once at severity 5 (score=5) if fixing the first one takes the same effort. The product of both gives you a ranked action list, not a gut feeling.

---

## 13. Choosing the One Fix

After ranking, the curriculum requires you to **pick exactly one fix and state your prediction before you implement it.**

Writing the prediction first is not a formality. It forces you to think through the causal chain. If your fix does not produce the predicted change, that tells you something important about your mental model of the system.

### Example Prediction Card

```
PROBLEM CHOSEN:       Cross-region contamination (ranked #1 by frequency x severity)

ROOT CAUSE DIAGNOSED: Queries without an explicit region filter have no
                      pre-filtering, so all 6 regional versions of
                      Section 4.2 compete in vector space. The one with
                      the highest cosine similarity wins, regardless of
                      correctness.

ONE CHANGE:           Add BM25 alongside vector search (hybrid/RRF).
                      BM25 will strongly uprank the chunk that contains
                      the user's exact region name if they mention it
                      ("US", "EMEA", etc.) in the query text.

PREDICTION:           hit-rate@3 will increase from X/8 to Y/8 for
                      region-specific questions where the region appears
                      in the query. No change expected for queries
                      without a region name (ambiguous queries).

WHAT THIS WILL NOT FIX: Citation format issues. Hallucination on edge
                         cases. Queries where the user does not mention
                         their region at all.
```

### Why One Change?

If you make three changes at once (add hybrid search + reranker + query rewriting) and hit-rate@3 improves by 25%, you don't know which change caused the improvement. Maybe two of them hurt and one helped by 75%. You've made future debugging harder.

One change = one number = clear causality.

---

## 14. Reference: What the Curriculum Wants You to Demonstrate

### Retrieval Debugging Checklist

| Requirement | Where to find evidence in this project |
|---|---|
| Label a specific failure as retrieval or generation | PARAMETERS block in the `policy-rag chat` command output shows retrieved_chunks sources |
| Make ONE change | Pick one: add BM25Retriever, or add FlagEmbeddingReranker, or add query rewriting |
| Before-and-after hit-rate@3 number | Run policy_rag/evaluation/chunking.py with the top_indices slice at [:3], before and after your change |
| Note which failures your change did NOT fix | Your change won't fix generation failures or ambiguous-region issues |

### Error Analysis Checklist

| Requirement | Where to find evidence in this project |
|---|---|
| Fair random sample (~20 queries) | Mix the 8 known-answer questions with adversarial queries, sample randomly |
| One honest sentence per failure, written before grouping | Do this in a running JSONL or markdown notes file, not retrospectively |
| Named problem groups a stranger understands | "Cross-region contamination", "Correct refusal", "Missing prerequisite clause" |
| Problems ranked by frequency x severity | Table format with Count, Severity, Score columns |
| One chosen target with a written prediction | Prediction card written before any code is touched |

---

## Quick Reference: Every Technique at a Glance

```
RETRIEVAL PIPELINE (in execution order)
========================================

1. USER QUERY
   |-- [optional] Query Rewriting (LLM cleans up messy query)
   |-- [optional] HyDE (LLM generates hypothetical answer, embed that instead)

2. CANDIDATE RETRIEVAL
   |-- Vector Search (BAAI/bge-small-en-v1.5 cosine similarity)  <- already in project
   |-- BM25 Keyword Search                                         <- add for hybrid
   |-- RRF Fusion of both lists                                    <- hybrid output

3. FILTERING (pre-vector, at index level)
   |-- ExactMatchFilter(region=...)                               <- already in project

4. RERANKING (post-retrieval, on top-K candidates)
   |-- Cross-encoder (bge-reranker-base)                          <- add for reranking

5. MERGING
   |-- AutoMergingRetriever (child -> parent context)             <- already in project

6. DIVERSITY (optional, inside retrieval step)
   |-- MMR (lambda approx 0.7 balances relevance and diversity)   <- optional add

7. GENERATION
   |-- Gemini Flash + citation-enforcing prompt + forced refusal  <- already in project


MEASUREMENT FORMULAS
====================
hit-rate@k  = (correct doc in top-k per query) / total queries
recall@k    = (correct docs in top-k) / (all correct docs in corpus)
MRR         = mean(1 / rank of first correct doc across all queries)


FAILURE DIAGNOSIS DECISION TREE
================================
Look at retrieved_chunks in the PARAMETERS output.
|
|-- Is the correct source file in the retrieved chunks?
    |
    |-- YES -> Is the answer correct?
    |          |
    |          |-- YES -> CORRECT (not a failure)
    |          |-- NO  -> GENERATION FAILURE (fix prompt, context, or LLM)
    |
    |-- NO  -> RETRIEVAL FAILURE (fix chunking, embedding, filtering, or hybrid)
```

---

## Further Reading From This Project

| File | What to study there |
|---|---|
| [policy_rag/evaluation/chunking.py](../policy_rag/evaluation/chunking.py) | The hit-rate@5 calculation — extend to k=3 for the retrieval benchmark |
| [policy_rag/retrieval/engine.py](../policy_rag/retrieval/engine.py) | Where to add BM25Retriever, FlagEmbeddingReranker, QueryFusionRetriever |
| [docs/evaluation-results.md](evaluation-results.md) | Section 2 has your before-after table template; Section 7 is the precision/completeness case study |
| [policy_rag/corpus/chunking.py](../policy_rag/corpus/chunking.py) | The concrete diff between naive (bad) and structure-aware (good) chunking |
| [policy_rag/evaluation/smoke.py](../policy_rag/evaluation/smoke.py) | 3 end-to-end checks; the answer-quality suite expands this to 20 traces |
| [docs/feature-backlog.md](feature-backlog.md) | Known failure modes already catalogued — the error taxonomy started here |
