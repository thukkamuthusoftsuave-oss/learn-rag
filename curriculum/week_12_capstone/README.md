<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Variant C: Policy Answer Desk

> **Enterprise HR Policy Assistant** fielding 700 questions/month across India and UK shared-services.  
> Integrates RAG retrieval, a ReAct agent loop, Model Context Protocol (MCP) tool serving, PII telemetry redaction, and a 30-case regression eval suite behind a single entry point.

---

## ⚡ Quickstart: The Stranger's 30-Second Guide

Clone or navigate to the repository and run the single entry point. **Zero configuration required** (works out-of-the-box offline or with OpenAI):

```powershell
# 1. Run the full 30-case integration eval suite in ONE command:
python curriculum/week_12_capstone/app.py --eval

# 2. Run a live query for an employee in India (Priya, Grade 3):
python curriculum/week_12_capstone/app.py --query "How many weeks of maternity leave am I entitled to?" --employee EMP-IN-001

# 3. Run a query for an employee in the UK (Eleanor, Grade 6):
python curriculum/week_12_capstone/app.py --query "What is my notice period under company policy?" --employee EMP-UK-001

# 4. Start the interactive console:
python curriculum/week_12_capstone/app.py --interactive
```

---

## 🎯 Key Capabilities Verified

1. **Grade & Entity Resolved BEFORE Answering:**  
   The agent executes `get_employee_record` via MCP first. It will never guess an employee's grade band or jurisdiction from conversational text.
2. **Entity Annex Silently Beats Handbook:**  
   Where General Handbook conflicts with India or UK Statutory Annexes (e.g. 12-week vs 26-week maternity leave; 4-week vs 12-week statutory notice), the Entity Annex **silently wins**.
3. **Explicit Clause, Version, & Effective Date Citations:**  
   Every citation includes:
   - Clause identifier (e.g., `Clause 2.1 (Maternity Benefit Override)`)
   - Policy version (e.g., `HR-LEAVE-2025-v2.0` or retrospective `HR-LEAVE-2024-v1.0`)
   - Policy effective date (e.g., `2025-01-01` or `2024-01-01`)
4. **Discretionary Questions Handed to HRBP:**  
   The assistant will **never** guess or hallucinate on discretionary policy exceptions (compassionate leave >5 days, sabbatical splits, negative leave advances). It executes `escalate_to_hrbp()` and returns a traceable ticket.
5. **Adversarial Colleague Leak Refusal:**  
   Employees querying a named colleague's grade or entitlement receive an immediate refusal without disclosing the colleague's grade band or existence.
6. **PII Redaction Line Held:**  
   Audit telemetry redacts `grade`, `base_salary`, and `leave_balances` (`[REDACTED_PII]`) across all logs.

---

## 📂 Deliverables & Submission Checklist

All Capstone artifacts required for the Week 12 AI Summit defense are organized in this folder:

| Artifact | File Path | Description |
|---|---|---|
| **Single Entry Point** | [`app.py`](file:///d:/learn-rag/curriculum/week_12_capstone/app.py) | CLI entry point supporting `--eval`, `--query`, and `--interactive`. |
| **Seam List** | [`seam_list.md`](file:///d:/learn-rag/curriculum/week_12_capstone/seam_list.md) | Tuesday's unedited seam list (fixed, accepted, ran-out-of-time). |
| **Architecture Sketch** | [`architecture.md`](file:///d:/learn-rag/curriculum/week_12_capstone/architecture.md) | System diagram, model calls, money flow, and PII boundary. |
| **Eval Report** | [`eval_report.md`](file:///d:/learn-rag/curriculum/week_12_capstone/eval_report.md) | 30 test cases, 100% pass, 100% judge agreement, stated non-coverage. |
| **Error Taxonomy** | [`taxonomy.md`](file:///d:/learn-rag/curriculum/week_12_capstone/taxonomy.md) | 5 modes with trace IDs, frequencies, and new integration mode. |
| **Trajectory Eval** | [`trajectory_eval.md`](file:///d:/learn-rag/curriculum/week_12_capstone/trajectory_eval.md) | 12 cases, 100% tool-choice accuracy, 8.3% outcome-vs-trajectory gap. |
| **End-to-End Trace** | [`trace_example.json`](file:///d:/learn-rag/curriculum/week_12_capstone/trace_example.json) | Complete trace with span latency, tokens, cost, and PII held. |
| **Known Weaknesses** | [`weaknesses.md`](file:///d:/learn-rag/curriculum/week_12_capstone/weaknesses.md) | Top 3 known weaknesses dated Wednesday, unprompted. |
| **10× Plan & Cost** | [`tenx_and_cost.md`](file:///d:/learn-rag/curriculum/week_12_capstone/tenx_and_cost.md) | Cost per question ($0.00015) + what breaks at 4,000 employees. |
| **Fresh-Eyes Review** | [`fresh_eyes_review.md`](file:///d:/learn-rag/curriculum/week_12_capstone/fresh_eyes_review.md) | Reviewer notes from Squad B (stumbles and fixes). |
| **Demo & Defense** | [`demo_script.md`](file:///d:/learn-rag/curriculum/week_12_capstone/demo_script.md) | 10-minute 4-part demo script + hostile questions defense. |

---

## 🛠️ MCP Capability Server

To run the standalone Model Context Protocol (MCP) server exposed to external agents and squads:

```powershell
python curriculum/week_12_capstone/hr_policy_mcp_server.py
```

Exposes 4 runtime tools via standard MCP JSON-RPC protocol:
- `get_employee_record`: Resolves grade (1–7), entity (`India`/`UK`), and tenure.
- `check_leave_balance`: Queries remaining leave balances by type.
- `search_policy_docs`: Entity-scoped hybrid search with 2024/2025 version arbitration.
- `escalate_to_hrbp`: Dispatches unresolved or discretionary inquiries to HR business partners.

---

## 👥 Valid Demo Employee IDs

- `EMP-IN-001`: Priya Sharma — India, Grade 3 (Senior Software Engineer, 3.2 yrs tenure)
- `EMP-UK-001`: Eleanor Vance — United Kingdom, Grade 6 (Engineering Director, 5.8 yrs tenure)
- `EMP-IN-002`: Rajesh Kumar — India, Grade 1 (Junior Support Analyst, 0.8 yrs tenure)
- `EMP-UK-002`: Oliver Smith — United Kingdom, Grade 2 (HR Coordinator, 1.5 yrs tenure)
- `EMP-IN-003`: Anita Desai — India, Grade 7 (VP of Operations, 8.0 yrs tenure)
- `EMP-INJECT-99`: Adversarial test profile with prompt injection in title.
