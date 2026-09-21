# Before/After Evaluation Delta Report

> **Overall Score:** 85.0% -> **100.0%** (+15.0%)

## 1. Score Delta by Problem Type

| Problem Type | Before Score | After Score | Score Delta (Δ) | Passing / Total | Status |
|---|---:|---:|---:|---:|:---:|
| **Core Entitlement** | 100.0% | **100.0%** | **+0.0%** | 8/8 | STABLE |
| **Edge Qualification** | 62.5% | **100.0%** | **+37.5%** | 8/8 | IMPROVED |
| **Refusal Safety** | 100.0% | **100.0%** | **+0.0%** | 4/4 | STABLE |

## 2. Fixed Failure Modes (Resolved Bugs)

### [FIXED] `EDGE-01`: I am a part-time employee (20 hours/week) in the US and I have worked here for 3 years. How many carry-over days do I get?
- **Problem Type:** edge_qualification
- **AI Judge Score:** 5/5 (Verdict: PASS)
- **Judge Reasoning:** All 3 expected policy facts present and verified.

### [FIXED] `EDGE-02`: What happens to my carry-over balance if I resign without notice in NA?
- **Problem Type:** edge_qualification
- **AI Judge Score:** 5/5 (Verdict: PASS)
- **Judge Reasoning:** All 2 expected policy facts present and verified.

### [FIXED] `EDGE-07`: What is the sabbatical duration and eligibility in EMEA?
- **Problem Type:** edge_qualification
- **AI Judge Score:** 5/5 (Verdict: PASS)
- **Judge Reasoning:** All 2 expected policy facts present and verified.

## 3. Regression Analysis

**Zero regressions detected.** Every test case that passed previously continues to pass.

## 4. What This Change Solved & What Remains

### What the Change Fixed:
1. **Precondition & Eligibility Guidance (`EDGE-01`)**: Prioritizing eligibility exclusions 
   (Section 4.7) before evaluating Section 4.2 cap tables stops the model from erroneously awarding 
   tenure caps to disqualified part-time staff.
2. **Multi-Fact Entitlement Completeness (`EDGE-07`)**: Sabbatical tenure requirements and duration 
   are now reported together without omitting the prerequisite milestone.

### What Remains (Out of Scope for Prompt Fixes):
- Fully ambiguous queries with no region named (`HARD-04`) cannot be fixed by prompt changes alone; 
  they require region auto-detection or interactive clarification.
