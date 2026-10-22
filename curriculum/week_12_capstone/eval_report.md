<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Integration Eval Suite Report

**Project:** Variant C · Policy Answer Desk (HR Policy Shared-Services)  
**Evaluator Run:** Integrated End-to-End Test Harness (`run_capstone_eval.py`)  
**Sample Size:** $N = 30$ curated end-to-end integration test cases  
**Date of Run:** 2026-10-12

---

## 1. Executive Summary

| Metric | Target | Integrated Result | Status |
|---|---|---|---|
| **Total Test Cases ($N$)** | 25–40 | **30 cases** | Passed |
| **Overall Pass Rate** | $\ge 90\%$ | **100.0% (30 / 30)** | Passed |
| **Judge Agreement vs Hand Labels** | $\ge 85\%$ | **100.0% (30 / 30)** | Passed |
| **PII Redaction Assertion Rate** | 100% | **100.0% (30 / 30)** | Passed |
| **Trace ID Survival Rate** | 100% | **100.0% (30 / 30)** | Passed |

---

## 2. Pass Rate per Taxonomy Mode

The 30 test cases directly target the five named error modes of the HR Policy system:

| Error Mode Targeted | Cases ($n$) | Passed | Pass Rate | Key Failure Mode Guarded |
|---|---|---|---|---|
| **`SUPERSEDED_VERSION_CITATION`** | 6 | 6 | **100.0%** | Quoting 2024 policy in 2025; failing to cite version and effective date. |
| **`ENTITY_ANNEX_OVERRIDE_MISSED`** | 6 | 6 | **100.0%** | General handbook 12-wk maternity quoted instead of India 26-wk statutory; UK notice period overrides. |
| **`PRE_RESOLVE_GRADE_OMISSION`** | 6 | 6 | **100.0%** | Answering entitlement without resolving employee grade band (Grades 1–7) via record lookup. |
| **`DISCRETIONARY_OVERCONFIDENCE`** | 6 | 6 | **100.0%** | Guessing on compassionate leave >5 days, sabbatical splits, or negative leave advances instead of HRBP handoff. |
| **`INTEGRATION_TOOL_RECORD_ANNEX_DESYNC` & Adversarial Leak** | 6 | 6 | **100.0%** | Dropping entity scope across MCP tool boundary; revealing colleague grade on adversarial inquiry. |
| **Total** | **30** | **30** | **100.0%** | — |

---

## 3. Validated Judge Agreement vs Hand Labels

To ensure the automated evaluation assertions are trustworthy in an HR compliance context, all 30 outputs were scored independently by an automated assertion judge and evaluated against frozen human gold-standard annotations.

$$\text{Judge Agreement Rate} = \frac{\text{Concordant Labels}}{\text{Total Cases}} = \frac{30}{30} = 100.0\%$$

- **Agreement Threshold:** Rubric requires $\ge 85\%$.
- **Achieved:** $100.0\%$ concordant agreement across all 30 test cases.
- **Evaluation Criteria Enforced by Judge:**
  1. **Citation Completeness:** Does the output contain an exact clause citation (e.g., `Section 4.1`, `Clause 2.1`) AND policy version (`HR-LEAVE-2025-v2.0` or `HR-LEAVE-2024-v1.0`) AND effective date (`2025-01-01` or `2024-01-01`)?
  2. **Entity Precedence:** Did the India or UK Annex win over the general handbook where statutory conflicts exist?
  3. **Tool Dispatch Truth:** Was `get_employee_record` invoked prior to entitlement synthesis?
  4. **Discretionary Escalation:** Was `escalate_to_hrbp` invoked with ticket generation on discretionary conditions?
  5. **Adversarial Non-Disclosure:** Did the response refuse without leaking the colleague's grade band or entitlement?

---

## 4. Stated Non-Coverage (What This Suite Does NOT Measure)

> [!WARNING]
> **Adjectives score zero. Here is the explicit, boundary-accurate statement of what our eval suite does not cover:**

1. **UK Employment Tribunal & India Labour Court Case Law:**  
   The suite does NOT test whether policy clauses comply with evolving judicial precedents or ongoing litigation (e.g., unwritten custom-and-practice exceptions established by specific department heads).
2. **TUPE Business Transfers & Mergers:**  
   The suite assumes full-time permanent employment under standard entity terms. It does NOT evaluate employees grandfathered under prior acquired company terms (TUPE regulations in the UK).
3. **Cross-Border Tax Residency Implications:**  
   While the system correctly cites sabbatical eligibility (unpaid leave up to 3 or 6 months), it does NOT evaluate whether an employee taking unpaid leave outside their contracting country triggers local permanent establishment or tax withholding complications.
4. **Contractor / Freelance / Zero-Hour Disputes:**  
   The corpus is bounded to Grades 1–7 full-time employees. Contractors querying the desk receive a standard employee entitlement answer unless filtered at the authentication gateway.
5. **Multi-Jurisdiction Hybrid Secondments:**  
   Employees on temporary international secondment (e.g., India-contracted employee physically stationed in London for 4 months) are evaluated under their primary contract entity (`employee.entity`), not dynamic GPS location.

---

## 5. Execution Command

To re-run the full 30-case integration eval suite in a single command:

```powershell
python curriculum/week_12_capstone/app.py --eval
```
*(or via the test harness directly: `python curriculum/week_12_capstone/run_capstone_eval.py`)*
