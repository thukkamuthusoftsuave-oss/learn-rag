# Week 1: Corpus Generation & Naive Chunking Baseline

## 1. Learning Objectives
- Design and generate a reproducible, multi-jurisdiction synthetic policy corpus (**HR-207 Policy Addenda** across 6 regions).
- Implement baseline **Naive Chunking** (fixed-line / fixed-token splitting).
- Establish standard baseline retrieval evaluation metrics: **Hit-in-Top-K** retrieval scoring.
- Identify the critical failure mode of naive chunking: **Boundary Fragmentation**.

---

## 2. Theoretical Background

### Why Synthetic Corpora for RAG Learning?
Real-world policy corpuses often contain messy proprietary data with unverified edge cases. A strictly formatted synthetic corpus allows us to:
1. Guarantee ground-truth answers for every question.
2. Control subtle variations between jurisdictions (e.g., UK notice laws vs US carry-over rules).
3. Benchmark chunking and retrieval algorithms deterministically before introducing LLMs.

### The Naive Chunking Trap
Naive chunking splits raw document text at arbitrary fixed line or character increments (e.g., 4 lines or 256 tokens) with or without window overlap.

While simple to implement:
- **Boundary Fragmentation**: If an entitlement table (e.g., Section 4.2 Carry-over Caps) spans 6 lines and the chunker cuts at line 4, the conditions (employee type, tenure) are stranded in Chunk A while the caps (number of days) land in Chunk B.
- **Lost Context**: Neither chunk contains sufficient semantic information for embedding models or lexical matchers to retrieve the full prerequisite clause.

---

## 3. Code Architecture

- [`naive_chunker.py`](file:///d:/learn-rag/curriculum/week_01_corpus_and_naive_chunking/naive_chunker.py): Core naive splitting algorithm using sliding windows over non-empty lines.
- [`run_eval.py`](file:///d:/learn-rag/curriculum/week_01_corpus_and_naive_chunking/run_eval.py): Evaluator measuring Hit-in-Top-5 using TF-IDF vectorization and Cosine Similarity against the 8 golden core queries.

---

## 4. How to Run

```powershell
python curriculum/week_01_corpus_and_naive_chunking/run_eval.py
```

### Expected Output:
- Scans `data_and_benchmarks/files_to_learn/synthetic_corpus/`
- Generates 82 naive chunks
- Reports Hit-in-Top-5 performance against `core_queries.json`
