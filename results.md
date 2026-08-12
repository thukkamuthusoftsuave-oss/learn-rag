# Results

> Updated 2026-08-12: corpus expanded (6 addenda, 60–64 lines each, sections 4.1–4.9), pipeline is now CLI-driven (`cli.py`), and every query returns an observability envelope. All numbers and transcripts below were re-observed on the expanded corpus.

## 1. Questions & Answers

The 8 known-answer questions were written before any retrieval ran and are unchanged.

| Q# | Question | Known-Correct Policy ID & Section |
|----|----------|-----------------------------------|
| 1 | What is the carry-over cap for a probationary employee in NA? | HR-207 Section 4.2 |
| 2 | What is the carry-over cap for a regular employee with 1 year of service in EMEA? | HR-207 Section 4.2 |
| 3 | What is the carry-over cap for a senior employee in APAC? | HR-207 Section 4.2 |
| 4 | When does the HR-207 policy become effective in LATAM? | Header (Effective Date) |
| 5 | What defines continuous service in US for the carry-over policy? | HR-207 Section 4.1 |
| 6 | Who is eligible for the sabbatical in UK? | HR-207 Section 4.3 |
| 7 | What is the max carry-over for a senior with > 2 years of service in US? | HR-207 Section 4.2 |
| 8 | Does a regular employee in NA get 15 days carry-over cap? | HR-207 Section 4.2 |

## 2. Hit-in-Top-5 Retrieval Evaluation

Both chunkers were run with the same queries using standard TF-IDF and cosine similarity to select the top 5 chunks (`python cli.py eval`). The table reflects whether the known-correct section appeared in the top 5 chunks.

| Chunker Strategy | Hit-in-Top-5 (X/8), original corpus | Hit-in-Top-5 (X/8), expanded corpus |
|------------------|-------------------------------------|-------------------------------------|
| Naive Chunker (4-line split) | 5/8 | **1/8** |
| Structure-Aware Chunker (Header split) | 8/8 | **8/8** |

The expanded corpus widened the gap: with ~4x more content, naive 4-line chunks fragment the eligibility tables even further and the fragments drown among competing chunks, while section-cohesive chunks still retrieve perfectly. Per-question dump (expanded corpus): naive hit only Q6; structure-aware hit all 8.

## 3. Metadata Filtering Impact

**Query:** "What is the max carry-over for a senior with > 2 years of service?"

**Unfiltered Results (Top 2):**
- Score: 0.2006 | Region: LATAM | Chunk: addendum_LATAM.txt_HR-207_Section_4.2
- Score: 0.1921 | Region: US | Chunk: addendum_US.txt_HR-207_Section_4.1

**Filtered Results (Region=US) (Top 2):**
- Score: 0.2369 | Region: US | Chunk: addendum_US.txt_HR-207_Section_4.2
- Score: 0.2284 | Region: US | Chunk: addendum_US.txt_HR-207_Section_4.1

*Filtering by region `US` moves the US Section 4.2 chunk to rank 1, guaranteeing the RAG uses the appropriate cap.*

## 4. Cited Answers and Refusals

All transcripts re-observed on 2026-08-12 via `python cli.py query` (Gemini `models/gemini-flash-latest`, index: 74 nodes / 62 leaves).

### Cited Answers
1. **Q:** "What is the carry-over cap for a probationary employee?" (region=US)
   **A:** "The carry-over cap for a probationary employee (with continuous service of less than 6 months) is 5 days. [[2 - Carry-over Cap]](addendum_US.txt)"

2. **Q:** "Who is eligible for the sabbatical in UK?"
   **A:** "In the UK, employees are eligible for a 6-week sabbatical after 10 years of service. [[HR-207 Section 4.3]](HR-207:addendum_UK.txt)"

3. **Q:** "Does a regular employee in NA get 15 days carry-over cap?" (region=NA)
   **A:** "No, a regular employee in NA does not get a 15-day carry-over cap. According to the policy, regular employees (those with 6 months to 2 years of service) have a 10-day cap…" [[addendum_NA.txt]]

### Refusal Transcripts
1. **Q:** "What is the maternity leave policy in EMEA?"
   **A:** "I'm sorry, I cannot answer that question based on the provided documents."

2. **Q:** "Who is eligible for a sabbatical in LATAM?"
   **A:** "I'm sorry, I cannot answer that question based on the provided documents."

3. **Q:** "What is the reimbursement limit for home office equipment?"
   **A:** "I'm sorry, I cannot answer that question based on the provided documents."

## 5. Chunking Code Diff
Unchanged from the original submission — `chunker.py` was not modified by the CLI/corpus work. The diff adding `structure_aware_chunker` (section-header split + metadata fields) remains the reference implementation.

## 6. Chunker Decision
We are keeping the **structure-aware chunker**.
The naive 4-line chunker severely fragmented eligibility tables across multiple chunks and regularly separated clause statements from their parent section numbers (i.e. severing the entitlement from the policy). The structure-aware chunker parses out the section headers and treats each section (and its embedded table) as a single, cohesive chunk, guaranteeing that every retrieved hit points explicitly to a policy rule. The expanded corpus made the gap larger, not smaller: **naive fell from 5/8 to 1/8 while structure-aware held at 8/8**, confirming the decision scales with corpus size.

## 7. Bonus Challenge: Precision/Completeness Tension
**Scenario**: *"I am a part-time employee (20 hours/week) in the US and I have worked here for 3 years. How many carry-over days do I get?"*

**Original diagnosis** (small corpus): the structure-aware chunker retrieved *HR-207 Section 4.2* (the cap) but stranded *Section 4.1* (the continuous-service definition requiring 40 hrs/week), so the model confidently answered "20 days" — precise on the rule, incomplete on the prerequisite definition.

**Observed on the expanded corpus** (2026-08-12, region=US): the model answered correctly —

> "Part-time employees working fewer than 40 hours per week do not meet the continuous-service definition and are not eligible for carry-over. This exclusion applies regardless of tenure or employee type. Therefore, you do not receive any carry-over days (0 days). [[HR-207 Section 4.7]](HR-207:addendum_US.txt)"

Two mechanisms fixed it: (a) the expanded US addendum makes the exclusion explicit in Section 4.7, which retrieves directly on "part-time"; (b) the production pipeline's `AutoMergingRetriever` merges child hits back into parent context, so neighboring sections travel together. The general lesson stands: tight structural chunks retrieve the literal rule but can strand prerequisite definitions — sibling-context merging or explicit cross-references are the mitigation.

## 8. CLI & Observability Envelope

The pipeline is now driven by `cli.py`:

```
python cli.py setup-data                 # regenerate data/*.txt
python cli.py ingest [--keep]            # rebuild index (fresh wipe unless --keep)
python cli.py query "<q>" [--region R] [--top-k N] [--json]
python cli.py eval                       # chunker bake-off (section 2)
python cli.py verify                     # refusal + region-filter + bonus checks
```

Every query returns an observability envelope alongside the answer. Example (region=US, probationary cap):

```
PARAMETERS
----------
region_filter : US
top_k         : 5
is_refusal    : False
tokens        : prompt=891 completion=41 total=932 (estimated-tiktoken)
latency_ms    : 18717
llm_model     : models/gemini-flash-latest
embed_model   : BAAI/bge-small-en-v1.5
timestamp     : 2026-08-12T20:36:14.974122+00:00
retrieved_chunks (4):
  [1] score=0.6785 source=addendum_US.txt node=50181a53-...
  ...
```

Token counts are tiktoken-based estimates (`estimated-tiktoken`) because the llama-index Gemini integration does not reliably surface provider usage metadata; the `method` field makes that explicit. `--json` emits the full envelope as machine-readable JSON.
