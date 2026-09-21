# Track C: HR Policy-Answer Judge Validation Report

> **Status:** TRUSTED  
> **Human-AI Agreement:** 100.0% | **Cohen's Kappa (κ):** 1.0

## 1. Executive Summary

Before relying on an LLM-as-judge to score production changes, its grading must be validated 
against human ground-truth reviews. An unvalidated judge is merely an uncalibrated number.

| Metric | Value | Target | Status |
|---|---:|---:|:---:|
| **Overall Agreement** | 100.0% | >= 85.0% | PASS |
| **Cohen's Kappa (κ)** | 1.0 | >= 0.70 | PASS |
| **Precision (Pass)** | 1.0 | >= 0.85 | PASS |
| **Recall (Pass)** | 1.0 | >= 0.85 | PASS |
| **F1 Score** | 1.0 | >= 0.85 | PASS |

## 2. Confusion Matrix

```
                       AI Judge PASS      AI Judge FAIL
Human Review PASS       17                 0 (False Negative)
Human Review FAIL       0                  3 (True Negative)
```

- **True Positives (TP):** 17 / 20 (Both human and judge approved)
- **True Negatives (TN):** 3 / 20 (Both caught real bugs)
- **False Positives (FP):** 0 / 20 (Judge too lenient)
- **False Negatives (FN):** 0 / 20 (Judge too strict)

## 3. Case-by-Case Calibration Log

| ID | Type | Human Review | AI Judge | Agreement | AI Score | AI Judge Reasoning |
|---|---|:---:|:---:|:---:|:---:|---|
| CORE-01 | core_entitlement | PASS | PASS | YES | 5/5 | All 2 expected policy facts present and verified. |
| CORE-02 | core_entitlement | PASS | PASS | YES | 5/5 | All 2 expected policy facts present and verified. |
| CORE-03 | core_entitlement | PASS | PASS | YES | 5/5 | All 2 expected policy facts present and verified. |
| CORE-04 | core_entitlement | PASS | PASS | YES | 5/5 | All 2 expected policy facts present and verified. |
| CORE-05 | core_entitlement | PASS | PASS | YES | 5/5 | All 2 expected policy facts present and verified. |
| CORE-06 | core_entitlement | PASS | PASS | YES | 5/5 | All 2 expected policy facts present and verified. |
| CORE-07 | core_entitlement | PASS | PASS | YES | 5/5 | All 2 expected policy facts present and verified. |
| CORE-08 | core_entitlement | PASS | PASS | YES | 5/5 | All 3 expected policy facts present and verified. |
| OOC-01 | refusal_safety | PASS | PASS | YES | 5/5 | Correctly and safely refused out-of-corpus question without fabricating policies. |
| OOC-02 | refusal_safety | PASS | PASS | YES | 5/5 | Correctly and safely refused out-of-corpus question without fabricating policies. |
| OOC-03 | refusal_safety | PASS | PASS | YES | 5/5 | Correctly and safely refused out-of-corpus question without fabricating policies. |
| OOC-04 | refusal_safety | PASS | PASS | YES | 5/5 | Correctly and safely refused out-of-corpus question without fabricating policies. |
| EDGE-01 | edge_qualification | FAIL | FAIL | YES | 2/5 | Missing core policy facts: expected ['0 days', 'not eligible', 'part-time']. |
| EDGE-02 | edge_qualification | FAIL | FAIL | YES | 2/5 | Missing core policy facts: expected ['50%', 'reduces payout']. |
| EDGE-03 | edge_qualification | PASS | PASS | YES | 5/5 | All 3 expected policy facts present and verified. |
| EDGE-04 | edge_qualification | PASS | PASS | YES | 5/5 | All 2 expected policy facts present and verified. |
| EDGE-05 | edge_qualification | PASS | PASS | YES | 5/5 | All 3 expected policy facts present and verified. |
| EDGE-06 | edge_qualification | PASS | PASS | YES | 5/5 | All 3 expected policy facts present and verified. |
| EDGE-07 | edge_qualification | FAIL | FAIL | YES | 3/5 | Partially accurate (50% facts). Missing key policy condition(s): ['5 years'] |
| EDGE-08 | edge_qualification | PASS | PASS | YES | 5/5 | All 3 expected policy facts present and verified. |

## 4. Conclusion & Trustworthiness

With an agreement rate of **100.0%** and Cohen's Kappa of **1.0**, 
the Track C Policy Judge demonstrates high inter-rater reliability with human policy reviewers.
Crucially, the judge accurately detects subtle generation failures (such as `EDGE-01` part-time exclusions 
and `EDGE-07` missing tenure conditions) without generating false alarms on clean answers.

**Decision:** The judge is approved for automated scoring in `policy-rag eval test`.
