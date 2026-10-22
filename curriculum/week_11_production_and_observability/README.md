# Week 11 — Production: Observability, Cost & the Failure-Test Loop

**Track C: HR Policy — "Find the wrong notice period in the logs"**  
**Module**: M6 Production & Capstone  
**Target Score**: 100 / 100

---

## 1. Problem Statement & The Support Drill

### The Customer Complaint
> *"An employee said it quoted the wrong notice period, maybe Tuesday."*  
> (No trace ID, no user ID, no exact timestamp).

### How It Was Located (Logs & Slice)
1. Filter slice: Full-text search over `output_response` in `logs/` for `notice period` and `30 days` matching Tuesday's traffic.
2. Result found: [trace_84f92a.json](file:///d:/learn-rag/curriculum/week_11_production_and_observability/logs/trace_84f92a.json) (or [trace.json](file:///d:/learn-rag/curriculum/week_11_production_and_observability/trace.json)).
3. **Time-to-Find**: **01:45** (1 minute, 45 seconds — well under the 5-minute requirement).

---

## 2. Root Cause Analysis

- **User Query**: *"I am planning to resign next week. I'm a senior director in the London office. How much notice period do I have to serve?"*
- **Erroneous Output**: *"Based on the handbook, your notice period is 30 days."* (Incorrect: standard director notice is 60 days under active policy).
- **Retrieved Context IDs**:
  - `HR-101_standard_notice`
  - `HR-102_manager_notice_superseded`
- **Root Cause**: The vector retriever fetched an outdated/superseded policy (`HR-102_manager_notice_superseded`). Because the agent was running on prompt version `v1.2_pre_effective_date_patch`, it lacked explicit instructions to prioritize newer effective dates over superseded policies.

---

## 3. The Failure-to-Test Loop (`eval_suite_drill.py`)

To ensure this bug never ships again, we converted this failure into a permanent evaluation case (`test_4`) in our regression test suite [eval_suite_drill.py](file:///d:/learn-rag/curriculum/week_11_production_and_observability/eval_suite_drill.py).

### Running the Evaluation Suite:
```powershell
python curriculum/week_11_production_and_observability/eval_suite_drill.py
```

### Output:
```text
--- Running Evaluation Suite (Prompt Version: v1.2_pre_effective_date_patch) ---
[PASS] test_1
[PASS] test_2
[PASS] test_3
[FAIL] test_4: expected '60 days', got '30 days'

SUITE RESULT: RED (3/4 passed)


--- Running Evaluation Suite (Prompt Version: v1.3_strict_effective_dates) ---
[PASS] test_1
[PASS] test_2
[PASS] test_3
[PASS] test_4: expected '60 days', got '60 days'

SUITE RESULT: GREEN (4/4 passed)
```

- **RED State**: 3/4 passed (the bug reproduces in pre-patch version).
- **GREEN State**: 4/4 passed (verified fixed with `v1.3_strict_effective_dates`).

---

## 4. Fix, Prompt Bump & Canary / Rollback Plan

- **Prompt Version Bump**: `v1.2_pre_effective_date_patch` $\to$ `v1.3_strict_effective_dates`
- **Canary Plan**:
  1. Route 10% of production traffic in the London office to prompt `v1.3_strict_effective_dates` for a 2-hour observation window.
  2. If the anomaly/failure rate exceeds 1% or user complaints occur, trigger an instant rollback to `v1.2_pre_effective_date_patch` via the feature-flag config map.

---

## 5. Cost Per Query Breakdown ([cost_by_stage.md](file:///d:/learn-rag/curriculum/week_11_production_and_observability/cost_by_stage.md))

| Stage | Latency (ms) | Tokens | Cost (USD) | Notes |
|---|---|---|---|---|
| **Retrieval (ChromaDB Vector DB)** | 250 ms | — | $0.00000 | Local embedded HNSW vector search |
| **Generation (LLM)** | 1,150 ms | 862 tokens | $0.00025 | Dominated by input context tokens |
| **Tools (HRIS API)** | 150 ms | — | $0.00005 | Employee record lookup |
| **Total Per Query** | **1,550 ms** | **862 tokens** | **$0.00030** | |

**Optimization**: Implement semantic caching for recurring policy questions (e.g. standard notice periods), eliminating LLM generation cost ($0.00000) for cache hits.

---

## 6. The 10x Scale Bottleneck ([tenx.md](file:///d:/learn-rag/curriculum/week_11_production_and_observability/tenx.md))

At **10x today's query volume** (scaling from 30 RPM to 300 RPM):
> **The LLM Provider Rate Limit (RPM) breaks first.**  
> The Tier 1 threshold is 200 RPM. At 300 RPM, it triggers systemic `HTTP 429 Too Many Requests` errors long before local ChromaDB or FastAPI compute resources reach capacity.

---

## 7. Deliverables Checklist

- [x] [drill.md](file:///d:/learn-rag/curriculum/week_11_production_and_observability/drill.md) — Support drill report with time-to-find (01:45) and slice filter used.
- [x] [trace.json](file:///d:/learn-rag/curriculum/week_11_production_and_observability/trace.json) & [logs/trace_84f92a.json](file:///d:/learn-rag/curriculum/week_11_production_and_observability/logs/trace_84f92a.json) — Full span breakdown with latency, tokens, cost, and retrieved IDs.
- [x] [eval_suite_drill.py](file:///d:/learn-rag/curriculum/week_11_production_and_observability/eval_suite_drill.py) — Regression eval script proving **RED (3/4)** $\to$ **GREEN (4/4)**.
- [x] [cost_by_stage.md](file:///d:/learn-rag/curriculum/week_11_production_and_observability/cost_by_stage.md) — Per-stage cost attribution table + semantic caching strategy.
- [x] [tenx.md](file:///d:/learn-rag/curriculum/week_11_production_and_observability/tenx.md) — 10x volume bottleneck with exact RPM numbers.
