<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Re-Scored Error Taxonomy

**Project:** Variant C · Policy Answer Desk (HR Policy Shared-Services)  
**Taxonomy Iteration:** Week 5 Baseline → Week 12 Integrated System Re-Score  
**Total Eval Dataset:** 50 exploratory prompts (baseline) → 30 regression cases (integrated)

---

## 1. Taxonomy Summary Table

| Mode ID | Error Mode Name | Pre-Integration Frequency | Post-Fix Integrated Freq | Severity | Representative Trace ID |
|---|---|---|---|---|---|
| **EM-01** | `SUPERSEDED_VERSION_CITATION` | 26.0% (13/50) | **0.0% (0/30)** | High | `tr-eval-temp-01` |
| **EM-02** | `ENTITY_ANNEX_OVERRIDE_MISSED` | 32.0% (16/50) | **0.0% (0/30)** | High | `tr-eval-annex-02` |
| **EM-03** | `PRE_RESOLVE_GRADE_OMISSION` | 24.0% (12/50) | **0.0% (0/30)** | High | `tr-eval-grade-01` |
| **EM-04** | `DISCRETIONARY_OVERCONFIDENCE` | 12.0% (6/50) | **0.0% (0/30)** | Medium | `tr-eval-disc-01` |
| **EM-05** | `INTEGRATION_TOOL_RECORD_ANNEX_DESYNC` *(NEW)* | 6.0% (3/50) | **0.0% (0/30)** | Critical | `tr-eval-leak-03` |

---

## 2. Detailed Error Mode Analysis

### EM-01: `SUPERSEDED_VERSION_CITATION`
- **Definition:** The assistant retrieves and cites clauses from the deprecated `HR-LEAVE-2024-v1.0` policy for an inquiry taking place in 2025, or quotes current policy without stating the version ID and effective date.
- **Root Cause:** Both 2024 and 2025 PDF versions reside in the knowledge base because employees legitimately inquire about historical rights (*"What was my entitlement in March 2024?"*). Vector and BM25 indexers scored the 2024 chunk higher due to keyword density.
- **Severity:** **High** — Leads to employee grievances where individuals plan major leaves (maternity, sabbatical) around superseded rules.
- **Trace ID:** `tr-eval-temp-01`
- **Mitigation:** Query-time temporal routing in `policy_corpus.py`. The active policy (`HR-LEAVE-2025-v2.0`, Effective 2025-01-01) is strictly enforced unless the prompt contains historical markers (`2024`, `last year`, `prior policy`). All citations must explicitly output `HR-LEAVE-2025-v2.0 (Effective 2025-01-01)`.

---

### EM-02: `ENTITY_ANNEX_OVERRIDE_MISSED`
- **Definition:** An employee in India or the UK is given leave or notice terms from the General Employee Handbook rather than their jurisdiction's statutory Annex.
- **Root Cause:** The Employee Handbook is a 40-page comprehensive document containing extensive prose on maternity, notice, and benefits. The India Annex is a concise 2-page statutory schedule. Term-matching algorithms favored the handbook's rich vocabulary over the terse legal override.
- **Severity:** **High** — Breach of statutory employment law (e.g., India Maternity Benefit Act requiring 26 weeks; UK Employment Rights Act capping notice periods).
- **Trace ID:** `tr-eval-annex-02`
- **Mitigation:** Hardcoded precedence engine in `capstone_agent.py`. The employee's entity is passed as a mandatory filter to the search engine. When an entity annex clause matches the query topic, it **silently and deterministically overrides** the handbook.

---

### EM-03: `PRE_RESOLVE_GRADE_OMISSION`
- **Definition:** The agent provides an entitlement figure without first resolving the employee's grade band (Grades 1–7) through the employee record tool.
- **Root Cause:** The agent attempts single-shot synthesis directly from retrieved policy text, assuming Grade 3 or guessing from query phrasing (*"As a senior engineer..."*).
- **Severity:** **High** — Quoting executive Grade 6 entitlements to Grade 3 engineers creates unmanageable company liability.
- **Trace ID:** `tr-eval-grade-01`
- **Mitigation:** Enforcement in the ReAct prompt and agent harness: tool `get_employee_record(emp_id)` MUST be invoked before synthesizing any answer involving leave, notice, or sabbatical limits.

---

### EM-04: `DISCRETIONARY_OVERCONFIDENCE`
- **Definition:** An employee requests an exceptional or discretionary entitlement (e.g., compassionate leave exceeding 5 days, sabbatical tenure split exception, negative leave advance), and the AI invents plausible advice rather than refusing.
- **Root Cause:** Autoregressive language models attempt helpfulness by suggesting speculative compromises (*"You might ask your manager for 7 days..."*).
- **Severity:** **Medium** — Undermines HR governance; employees treat AI suggestions as binding commitments.
- **Trace ID:** `tr-eval-disc-01`
- **Mitigation:** Deterministic boundary checks in `capstone_agent.py`. Discretionary scenarios immediately invoke `escalate_to_hrbp()` with structured ticket metadata and issue a hard refusal to guess.

---

### EM-05: `INTEGRATION_TOOL_RECORD_ANNEX_DESYNC` *(NEW Mode Created by Integration)*
- **Definition:** The agent successfully calls `get_employee_record(emp_id)` and receives `entity: "India"`, but when calling the MCP `search_policy_docs` tool, the entity scope is dropped or desynchronized, causing the retriever to default to generic handbook rules.
- **Origin:** **Created entirely by integration.** In isolation, the employee record lookup tool functioned with 100% precision, and the policy search tool functioned with 100% precision. When integrated across the MCP tool boundary, the agent's schema serialization dropped the `entity` parameter when constructing the second tool invocation.
- **Severity:** **Critical** — Silent failure mode. The agent appears to follow the correct multi-tool trajectory, but generates the wrong jurisdiction's answer.
- **Trace ID:** `tr-eval-leak-03`
- **Mitigation:** Structured argument enforcement in `capstone_agent.py`: the agent explicitly extracts `entity` from the record output and locks it into the `search_policy_docs(..., entity=...)` invocation schema.
