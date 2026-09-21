# Enterprise RAG & Agent Engineering Curriculum (Weeks 1 to 8)

This directory contains the modular, week-by-week implementation of all concepts taught across the 8-week curriculum. Each module is self-contained, fully runnable, and accompanied by detailed theoretical and practical documentation.

---

## Curriculum Overview

| Week | Module Topic | Core Engineering Concept | Benchmark / Key Outcome |
|---|---|---|---|
| **[Week 1](file:///d:/learn-rag/curriculum/week_01_corpus_and_naive_chunking)** | Corpus Generation & Naive Chunking | Synthetic multi-region corpus, line splitting | Identifies table fragmentation & low baseline hit-rate |
| **[Week 2](file:///d:/learn-rag/curriculum/week_02_structure_aware_chunking_and_metadata)** | Structure-Aware Chunking & Metadata | Header-aware parsing (`HR-207 Section X.Y`), metadata tags | Hit-in-Top-5 jumps to 8/8 (100%); region filtering eliminates noise |
| **[Week 3](file:///d:/learn-rag/curriculum/week_03_embeddings_and_hybrid_retrieval)** | Embeddings & Hybrid Retrieval | ChromaDB (`BAAI/bge-small-en-v1.5`), BM25, Reciprocal Rank Fusion | RRF fuses dense semantics + sparse keywords for exact-term retrieval |
| **[Week 4](file:///d:/learn-rag/curriculum/week_04_retrieval_debugging_and_failure_separation)** | Retrieval Debugging & Failure Separation | Retrieval Failure vs Generation Failure, deterministic refusal | Separates retriever bugs from prompt bugs; eliminates out-of-domain hallucinations |
| **[Week 5](file:///d:/learn-rag/curriculum/week_05_error_analysis_and_eval_taxonomy)** | Error Analysis & Evaluation Taxonomy | Closed 5-label error taxonomy, severity ranking | Generates actionable Prediction Cards by Frequency × Severity impact |
| **[Week 6](file:///d:/learn-rag/curriculum/week_06_advanced_rag_multiturn_and_query_condensation)** | Advanced RAG & Multi-Turn Chat | Contextual query condensation, session management | Rewrites ambiguous follow-up questions before retrieval; verifies citation tags |
| **[Week 7](file:///d:/learn-rag/curriculum/week_07_agent_vs_fixed_workflow)** | AI Agents vs Fixed Workflows | Hand-built ReAct loop vs Deterministic DAG workflow | 8 Numbers Table: Workflow is 3.3x faster, 8.7x fewer tokens, 6.7x cheaper |
| **[Week 8](file:///d:/learn-rag/curriculum/week_08_trajectory_eval_and_injection_defense)** | Trajectory Evals & Injection Defense | Outcome-vs-Trajectory Gap, 4-Layer Defense-in-Depth | Neutralizes indirect prompt injection; closes outcome-vs-trajectory gap |

---

## Running the Curriculum Demos

Each week's directory contains a dedicated evaluation script:

```powershell
# Week 1: Naive Chunking Baseline
python curriculum/week_01_corpus_and_naive_chunking/run_eval.py

# Week 2: Structure-Aware Chunking Bake-Off
python curriculum/week_02_structure_aware_chunking_and_metadata/run_eval.py

# Week 3: Hybrid Retrieval (Vector + BM25 + RRF)
python curriculum/week_03_embeddings_and_hybrid_retrieval/run_eval.py

# Week 4: Failure Separation & Refusal Engine
python curriculum/week_04_retrieval_debugging_and_failure_separation/run_eval.py

# Week 5: Error Taxonomy & Prediction Card
python curriculum/week_05_error_analysis_and_eval_taxonomy/run_eval.py

# Week 6: Multi-Turn Query Condensation & Citations
python curriculum/week_06_advanced_rag_multiturn_and_query_condensation/run_eval.py

# Week 7: ReAct Agent vs Fixed Workflow Race
python curriculum/week_07_agent_vs_fixed_workflow/run_race_benchmark.py

# Week 8: Trajectory Evaluation & Prompt Injection Defense
python curriculum/week_08_trajectory_eval_and_injection_defense/run_eval.py
```
