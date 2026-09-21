# Week 3: Embeddings & Hybrid Retrieval (BM25 + Dense + RRF)

## 1. Learning Objectives
- Build a persistent **ChromaDB** vector store using dense embeddings (`BAAI/bge-small-en-v1.5`).
- Implement sparse lexical retrieval with **BM25Okapi** (`rank-bm25`).
- Fuse dense and sparse rankings using **Reciprocal Rank Fusion (RRF)**.
- Measure retrieval quality using **Hit-Rate@1**, **Hit-Rate@3**, and **Mean Reciprocal Rank (MRR)**.

---

## 2. Theoretical Background

### Dense vs Sparse: The Complementary Trade-Off
- **Dense Embeddings (Vector Search)**: Map text into continuous vector representations. Excels at semantic meaning, synonyms, and intent (e.g. "vacation carry-over" matching "leave accumulation"). Fails on exact section numbers, serial IDs, or specific statutory thresholds.
- **Sparse Embeddings (BM25)**: Lexical frequency scoring based on term presence. Excels at exact tokens ("HR-207 Section 4.7", "20 hours per week"). Fails on paraphrasing and vocabulary mismatch.

### Reciprocal Rank Fusion (RRF)
Rather than trying to calibrate incompatible score magnitudes between cosine similarities ($[-1, 1]$) and BM25 scores ($[0, \infty)$), RRF fuses based on **ordinal ranks**:

$$\text{RRF\_Score}(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$

Where:
- $M = \{\text{Vector}, \text{BM25}\}$
- $r_m(d)$ is the 1-based rank of document $d$ in retriever $m$
- $k$ is a smoothing constant (standard default: 60)

Documents retrieved with high confidence across both retrievers rank highest.

---

## 3. Code Architecture

- [`vector_indexer.py`](file:///d:/learn-rag/curriculum/week_03_embeddings_and_hybrid_retrieval/vector_indexer.py): ChromaDB integration with HuggingFace `BAAI/bge-small-en-v1.5` dense embeddings.
- [`bm25_retriever.py`](file:///d:/learn-rag/curriculum/week_03_embeddings_and_hybrid_retrieval/bm25_retriever.py): Lexical BM25 ranker over tokenized policy text.
- [`hybrid_fusion.py`](file:///d:/learn-rag/curriculum/week_03_embeddings_and_hybrid_retrieval/hybrid_fusion.py): Reciprocal Rank Fusion algorithm combining dense and sparse candidate lists.
- [`run_eval.py`](file:///d:/learn-rag/curriculum/week_03_embeddings_and_hybrid_retrieval/run_eval.py): Evaluation script benchmarking Hit-Rate@1, Hit-Rate@3, and MRR.

---

## 4. How to Run

```powershell
python curriculum/week_03_embeddings_and_hybrid_retrieval/run_eval.py
```
