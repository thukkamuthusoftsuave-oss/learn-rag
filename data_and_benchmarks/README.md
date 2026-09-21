# Data & Benchmarks: Files to Learn and Test Responses

This directory contains all the foundational reference documents, golden benchmark datasets, human evaluation workbooks, raw test traces, and empirical evaluation reports developed across the 8-week curriculum.

---

## Directory Overview

```
data_and_benchmarks/
├── files_to_learn/                      # Ground truth files and study curriculum
│   ├── synthetic_corpus/                # 6 regional HR-207 policy addenda (US, UK, EMEA, APAC, LATAM, NA)
│   ├── golden_datasets/                 # Standardized evaluation questions (JSON)
│   ├── study_guides/                    # In-depth architectural & error analysis study guides
│   └── manual_review/                   # Human trace grading sheets and scoring workbook
│
└── test_responses/                      # Empirical outputs and benchmarks
    ├── benchmark_results/               # Trajectory evaluation CSVs, race comparisons, and deltas
    ├── deliverable_reports/             # Formal week-by-week technical deliverable reports
    └── trace_logs/                      # Observability envelopes and JSONL execution traces
```

---

## 1. Files to Learn (`files_to_learn/`)

### A. Synthetic Policy Corpus (`files_to_learn/synthetic_corpus/`)
Contains the six synthetic regional addenda for policy **HR-207 (Paid Time Off & Leave Entitlements)**:
- [`addendum_US.txt`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/synthetic_corpus/addendum_US.txt) — Standard US carry-over caps (5, 10, 15 days), 40 hr/week continuous service definition.
- [`addendum_UK.txt`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/synthetic_corpus/addendum_UK.txt) — Statutory notice periods (§ 4.5), 10-year sabbatical rule (6 weeks).
- [`addendum_EMEA.txt`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/synthetic_corpus/addendum_EMEA.txt) — 5-year sabbatical eligibility threshold (4 weeks).
- [`addendum_APAC.txt`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/synthetic_corpus/addendum_APAC.txt) — 20-hour part-time eligibility definition, statutory holidays.
- [`addendum_LATAM.txt`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/synthetic_corpus/addendum_LATAM.txt) — Effective dates, statutory forfeiture limitations.
- [`addendum_NA.txt`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/synthetic_corpus/addendum_NA.txt) — North American regional overrides and probation rules.

### B. Standardized Golden Datasets (`files_to_learn/golden_datasets/`)
Exported in clean, standard JSON formats for automated testing and model-free evaluation:
- [`core_queries.json`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/golden_datasets/core_queries.json): 8 core known-answer queries used for baseline hit-in-top-5 verification.
- [`hard_queries.json`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/golden_datasets/hard_queries.json): Retrieval stress tests (exact numerical thresholds and section numbers requiring BM25 hybrid search).
- [`refusal_queries.json`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/golden_datasets/refusal_queries.json): Out-of-corpus topics mandating deterministic refusal without hallucinations.
- [`edge_queries.json`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/golden_datasets/edge_queries.json): Complex qualification clauses (part-time workers, tenure cutoffs).
- [`week7_agent_10_questions.json`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/golden_datasets/week7_agent_10_questions.json): 10 employee entitlement questions comparing ReAct agent vs Fixed Workflow.
- [`week8_agent_20_cases.json`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/golden_datasets/week8_agent_20_cases.json): 20 comprehensive cases evaluating outcome-vs-trajectory gaps and prompt injections.

### C. In-Depth Study Guides (`files_to_learn/study_guides/`)
- [`study-qa-week4-week5.md`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/study_guides/study-qa-week4-week5.md): Comprehensive Q&A covering retrieval failure vs generation failure, error taxonomy, and debugging workflows.
- [`retrieval-and-error-analysis.md`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/study_guides/retrieval-and-error-analysis.md): Technical deep dive on hybrid retrieval, cross-encoders, and RRF mechanics.
- [`evaluation-results.md`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/study_guides/evaluation-results.md): Empirical benchmarks across naive vs structure-aware chunking and hybrid retrieval.
- [`feature-backlog.md`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/study_guides/feature-backlog.md): Architectural roadmap and prioritization matrix.

### D. Manual Review Workbooks (`files_to_learn/manual_review/`)
- [`week5-manual-review-sheet.md`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/manual_review/week5-manual-review-sheet.md): Manual review methodology for evaluating production traces.
- [`week5-manual-review.xlsx`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/manual_review/week5-manual-review.xlsx): Excel scoring spreadsheet with formulaic agreement metrics.

---

## 2. Test Responses & Benchmark Records (`test_responses/`)

### A. Benchmark Results (`test_responses/benchmark_results/`)
- [`week8_trajectory_eval.csv`](file:///d:/learn-rag/data_and_benchmarks/test_responses/benchmark_results/week8_trajectory_eval.csv): Complete 20-case evaluation matrix comparing the Baseline Agent vs Hardened Agent:
  - Outcome Pass Rate: **75.0% → 100.0%**
  - Trajectory Pass Rate: **55.0% → 100.0%**
  - Outcome-vs-Trajectory Gap: **20.0% → 0.0%** (Fully Closed)
  - Injection Attack Success Rate: **100.0% → 0.0%** (Neutralized)
- [`before-after-delta.md`](file:///d:/learn-rag/data_and_benchmarks/test_responses/benchmark_results/before-after-delta.md): Statistical delta between baseline and hardened system.
- [`judge-validation.md`](file:///d:/learn-rag/data_and_benchmarks/test_responses/benchmark_results/judge-validation.md): Human judge vs LLM evaluator agreement analysis.

### B. Deliverable Reports (`test_responses/deliverable_reports/`)
- [`week7_deliverables.md`](file:///d:/learn-rag/data_and_benchmarks/test_responses/deliverable_reports/week7_deliverables.md): Detailed comparison of ReAct Agent vs Fixed DAG Workflow (8 Numbers Table: 3.3x speedup, 8.7x fewer tokens, 6.7x cost savings for fixed workflows).
- [`week8_deliverables.md`](file:///d:/learn-rag/data_and_benchmarks/test_responses/deliverable_reports/week8_deliverables.md): Mentored check deliverables on the Outcome-vs-Trajectory Gap, indirect prompt injection defense, and OWASP LLM Top 10 residual risk analysis.

### C. Execution Trace Logs (`test_responses/trace_logs/`)
- [`traces.jsonl`](file:///d:/learn-rag/data_and_benchmarks/test_responses/trace_logs/traces.jsonl): Production query trace logs containing query texts, retrieved chunks, token metrics, latency, and error classification labels (`CORRECT`, `RETRIEVAL_FAILURE`, `GENERATION_FAILURE`, `CORRECT_REFUSAL`).

---

## 3. How to Use This Directory for Learning

1. **Study Failure Separation**: Read [`study_guides/study-qa-week4-week5.md`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/study_guides/study-qa-week4-week5.md) to understand why naive chunking and single-mode retrieval fail.
2. **Inspect the Golden Datasets**: Review [`golden_datasets/week8_agent_20_cases.json`](file:///d:/learn-rag/data_and_benchmarks/files_to_learn/golden_datasets/week8_agent_20_cases.json) to see how adversarial attacks (`EMP-INJECT-01` to `04`) are structured.
3. **Analyze Benchmark Deltas**: Compare the raw rows in [`benchmark_results/week8_trajectory_eval.csv`](file:///d:/learn-rag/data_and_benchmarks/test_responses/benchmark_results/week8_trajectory_eval.csv) against the narrative in [`deliverable_reports/week8_deliverables.md`](file:///d:/learn-rag/data_and_benchmarks/test_responses/deliverable_reports/week8_deliverables.md).
