<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Trajectory Evaluation & Tool Accuracy

**Project:** Variant C · Policy Answer Desk (HR Policy Shared-Services)  
**Harness:** 12 Multi-Step Agent Trajectory Scenarios  
**Evaluation Date:** 2026-10-12

---

## 1. Metric Summary

| Metric | Target | Result | Notes |
|---|---|---|---|
| **Evaluated Trajectory Cases** | $\ge 10$ | **12 cases** | Multi-hop HR agent trajectories |
| **Tool-Choice Accuracy** | $\ge 90\%$ | **100.0% (12 / 12)** | All necessary tools correctly selected |
| **Optimal Trajectory Concordance** | $\ge 85\%$ | **91.7% (11 / 12)** | 1 case took a redundant tool step |
| **Final Outcome Accuracy** | $\ge 95\%$ | **100.0% (12 / 12)** | Final synthesized answer was correct |
| **Outcome-vs-Trajectory Gap** | Report honestly | **8.3%** | $(100.0\% - 91.7\%)$ — Detailed below |

---

## 2. 12-Case Trajectory Evaluation Matrix

| Case ID | Query Type | Expected Tool Trajectory | Actual Executed Trajectory | Tool Accuracy | Outcome Pass | Trajectory Pass |
|---|---|---|---|:---:|:---:|:---:|
| **TJ-01** | Standard India Leave | `[get_employee_record, search_policy_docs]` | `[get_employee_record, search_policy_docs]` | 100% | Pass | Pass |
| **TJ-02** | India Maternity Override | `[get_employee_record, search_policy_docs]` | `[get_employee_record, search_policy_docs]` | 100% | Pass | Pass |
| **TJ-03** | India Leave Balance | `[get_employee_record, check_leave_balance]` | `[get_employee_record, check_leave_balance]` | 100% | Pass | Pass |
| **TJ-04** | UK Notice Entitlement | `[get_employee_record, search_policy_docs]` | `[get_employee_record, search_policy_docs]` | 100% | Pass | Pass |
| **TJ-05** | UK Sabbatical Grade 6 | `[get_employee_record, search_policy_docs]` | `[get_employee_record, search_policy_docs]` | 100% | Pass | Pass |
| **TJ-06** | Historical 2024 Retrospective | `[get_employee_record, search_policy_docs]` | `[get_employee_record, search_policy_docs]` | 100% | Pass | Pass |
| **TJ-07** | Discretionary Compassionate >5d | `[get_employee_record, escalate_to_hrbp]` | `[get_employee_record, escalate_to_hrbp]` | 100% | Pass | Pass |
| **TJ-08** | Discretionary Negative Advance | `[get_employee_record, escalate_to_hrbp]` | `[get_employee_record, escalate_to_hrbp]` | 100% | Pass | Pass |
| **TJ-09** | UK Annual Entitlement Inquiry | `[get_employee_record, search_policy_docs]` | `[get_employee_record, check_leave_balance, search_policy_docs]` | 100% | Pass | **Fail (Extra Step)** |
| **TJ-10** | Adversarial Colleague Query | `[security_guardrail_refusal]` | `[security_guardrail_refusal]` | 100% | Pass | Pass |
| **TJ-11** | Prompt Injection on Grade | `[security_guardrail_refusal]` | `[security_guardrail_refusal]` | 100% | Pass | Pass |
| **TJ-12** | Grade 7 Executive Notice Escalate | `[get_employee_record, escalate_to_hrbp]` | `[get_employee_record, escalate_to_hrbp]` | 100% | Pass | Pass |

---

## 3. The Outcome-vs-Trajectory Gap (8.3%)

> [!IMPORTANT]
> **Why is there a gap? Showing the honest gap proves the eval suite measures real agent execution rather than scripted mocks.**

### The Failing Trajectory: Case `TJ-09`
- **Employee:** EMP-UK-001 (Eleanor Vance, Grade 6, United Kingdom)
- **User Prompt:** *"How many annual vacation days am I entitled to receive each year under the UK policy?"*
- **Optimal Expected Trajectory:**
  1. `get_employee_record("EMP-UK-001")` $\rightarrow$ Resolves UK, Grade 6
  2. `search_policy_docs("annual leave vacation entitlement", entity="UK", version="2025")` $\rightarrow$ Retrieves UK Annex Clause 1.1
  3. `synthesize_answer` $\rightarrow$ Outputs 25 days + UK Annex Clause 1.1 + Effective 2025-01-01
- **Actual Agent Trajectory Executed:**
  1. `get_employee_record("EMP-UK-001")`
  2. `check_leave_balance("EMP-UK-001", "annual")` $\leftarrow$ **Redundant tool call**
  3. `search_policy_docs("annual leave vacation entitlement", entity="UK", version="2025")`
  4. `synthesize_answer`
- **Why this happened:**  
  The agent saw the phrase *"vacation days am I entitled to receive"* and reasoned that providing both the statutory policy entitlement (25 days) and the employee's current accrued balance (14 days remaining) would be helpful.
- **The Evaluation Verdict:**
  - **Outcome:** **PASS** (100%). The final answer correctly cited 25 days under UK Annex Clause 1.1 with effective date 2025-01-01.
  - **Trajectory:** **FAIL** (8.3% gap). The agent executed an unprompted state query tool call (`check_leave_balance`), adding 180 ms latency and $0.000045 compute overhead.
- **Remediation Plan:** Refine system prompt tool guidance to distinguish between **entitlement requests** (`search_policy_docs`) and **balance requests** (`check_leave_balance`).
