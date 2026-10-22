<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — 10-Minute Demo Script & Defense Guide

**Project:** Variant C · Policy Answer Desk (HR Policy Shared-Services)  
**Presenter:** AI Engineering Squad Lead  
**Timing:** 10 Minutes Live + 5 Minutes Panel Q&A  
**Rule:** *A flawless demo is a red flag. Show real failures, real seams, and hard numbers.*

---

## ⏱️ Timeline & Four-Part Demo Breakdown

```
00:00 ─── [Part 1: The Real Run (Live System)] ─── 02:30
02:30 ─── [Part 2: Real Failures We Found] ───────── 05:00
05:00 ─── [Part 3: Numbers That Moved] ──────────── 07:30
07:30 ─── [Part 4: What's Next & Defense] ───────── 10:00
```

---

## Part 1 — The Real Run (00:00 – 02:30)

### 1.1 Action: Run a Live Policy Entitlement Query
- **Speaker:**  
  *"Let's start with a real run on our single entry point. We have an employee in Chennai, India — Priya (EMP-IN-001, Grade 3) asking about maternity leave."*
- **Command:**
  ```powershell
  python curriculum/week_12_capstone/app.py --query "How many weeks of maternity leave am I entitled to?" --employee EMP-IN-001
  ```
- **What the Audience Sees:**
  1. `TOOL CALL 1: get_employee_record("EMP-IN-001")` $\rightarrow$ Resolves Entity: `India`, Grade: `3`.
  2. `TOOL CALL 2: search_policy_docs(..., entity="India", version="HR-LEAVE-2025-v2.0")`.
  3. Precedence Engine activates: The General Handbook grants 12 weeks, but the **India Entity Annex silently overrides it**.
  4. Response generated: **26 weeks of paid maternity leave**, citing:
     - 📜 **Clause:** `Clause 2.1 (Maternity Benefit Override)`
     - 🏷️ **Version:** `HR-LEAVE-2025-v2.0`
     - 📅 **Effective Date:** `2025-01-01`
  5. The PII Line held: Log entry shows `grade: [REDACTED_PII]` and `base_salary: [REDACTED_PII]`.

### 1.2 Action: Run a Discretionary Query (Hand Off to HRBP)
- **Speaker:**  
  *"Now let's ask a discretionary policy question. An employee asking for 10 days of compassionate leave for an uncle."*
- **Command:**
  ```powershell
  python curriculum/week_12_capstone/app.py --query "Can I take 10 days compassionate leave for an uncle?" --employee EMP-IN-001
  ```
- **What the Audience Sees:**
  1. `TOOL CALL 1: get_employee_record("EMP-IN-001")`.
  2. `TOOL CALL 2: escalate_to_hrbp(...)` $\rightarrow$ Ticket created: `HRBP-ESC-xxxxx`, SLA: 24h.
  3. Output: The assistant **refuses to guess** or grant discretionary approval. It hands off directly to an HR Business Partner with an audit ticket.

---

## Part 2 — The Failures We Found (02:30 – 05:00)

- **Speaker:**  
  *"If our app was flawless, we'd be hiding something. Here are the three real failures we discovered during integration:"*

### 2.1 The Superseded 2024 Policy Failure (Trace: `tr-eval-temp-01`)
- **The Failure:**  
  In baseline testing, an employee asked *"How much privilege leave do I get?"*. The retriever returned `HR-LEAVE-2024-v1.0` (15 days) instead of the 2025 policy (18 days). Both policies were in the index because employees legitimately ask about 2024. BM25 term frequency scored the 2024 chunk higher due to keyword density.
- **The Grievance Risk:**  
  Employees planning leave in 2025 based on 2024 quotas.
- **The Fix:**  
  Strict query-time temporal routing defaulting to active version `HR-LEAVE-2025-v2.0` unless explicitly asked about prior years.

### 2.2 The Real Tuesday Seam Bug: Substring Matcher Blew Up on `"advance"`
- **The Seam:**  
  Our colleague leak detector scanned employee surnames with naive substring matching (`name in query`). When an India Grade 3 asked: *"Can I request a leave advance?"*, the substring `"advance"` matched `"vance"` (Eleanor Vance, EMP-UK-001). The system blocked legitimate leave advance queries as hostile colleague eavesdropping!
- **The Fix:**  
  Replaced substring with regex word boundaries `\b{name}\b`.

### 2.3 The New Integration Mode: `INTEGRATION_TOOL_RECORD_ANNEX_DESYNC`
- **The Failure:**  
  Created entirely at the seam between the ReAct Agent and MCP server. The agent retrieved `entity: "India"` from the record tool, but dropped the entity parameter when calling the MCP `search_policy_docs` tool. Both tools worked in isolation; the integration seam dropped state.

---

## Part 3 — A Number That Moved (05:00 – 07:30)

- **Speaker:**  
  *"Here is what our integrated evaluation suite proves with hard numbers, not adjectives."*

### 3.1 Metrics Before vs After ($N = 30$ Integrated Cases)

| Metric | Pre-Integration Baseline | Post-Fix Integrated System | Delta ($\Delta$) |
|---|:---:|:---:|:---:|
| **Superseded 2024 Citation Rate** | 26.0% (13 / 50) | **0.0% (0 / 30)** | **-26.0%** (Eliminated) |
| **Entity Annex Override Failure Rate** | 32.0% (16 / 50) | **0.0% (0 / 30)** | **-32.0%** (Eliminated) |
| **Unresolved Grade Hallucination** | 24.0% (12 / 50) | **0.0% (0 / 30)** | **-24.0%** (Eliminated) |
| **Judge Agreement vs Hand Labels** | 71.4% | **100.0% (30 / 30)** | **+28.6%** (Exceeds 85% bar) |
| **Outcome-vs-Trajectory Gap** | — | **8.3%** | Honest 1-step excess |

### 3.2 What Our Suite Explicitly Does NOT Measure
- **Speaker:**  
  *"Let me tell you what our suite does NOT measure before you ask: It does not evaluate UK Employment Tribunal judicial case law, TUPE grandfathered transfers, cross-border tax residency on extended sabbaticals, or contractor dispute arbitration. We test policy as written, not case law in court."*

---

## Part 4 — What's Next & The 10× Plan (07:30 – 10:00)

### 4.1 Cost per Question
- **Input:** 420 tokens ($0.000063)
- **Output:** 125 tokens ($0.000075)
- **Total:** **$0.00015 / question** ($0.11 / month for the current 700 queries).

### 4.2 What Breaks First at 10× Scale (4,000 Employees)
- **Speaker:**  
  *"If HR rolls this to all 4,000 employees next Monday, what breaks first? Not the database, not the agent loop. It is OpenAI's rate limits on March 31 annual leave deadline morning. 600 employees hit the bot in 30 minutes $\rightarrow$ 1,200 RPM requiring 654,000 TPM. Tier 2 caps out at 80,000 TPM. The system throws HTTP 429 within 3.8 seconds."*
- **The Remediation:**  
  A Redis semantic cache absorbing 80% of repetitive leave deadline inquiries, reducing upstream load to 240 RPM.

---

## ⚔️ Defense of Hostile Panel Questions

### Question 1: *"It told a Grade 3 in Chennai they get the Grade 6 UK parental leave entitlement. How many of your eval cases pin BOTH grade and entity, and what do those cases score — not the average, those?"*
- **Our Answer:**  
  *"Exactly 12 of our 30 test cases explicitly test the intersection of Entity (India vs UK) and Grade (Grade 1, 3, 5, 6, 7). Those 12 cases score **100.0% (12/12)**. We enforce this through two architectural locks: first, `get_employee_record` runs deterministically before synthesis; second, the search engine enforces `entity_scope == employee.entity`. A Grade 3 in Chennai cannot retrieve UK Grade 6 clauses because UK-scoped chunks are physically pruned from the candidate set."*

---

### Question 2: *"An employee asks about their leave on 2 January. Which policy version does your retriever return? Is 'effective date' a filter your code enforces, or is it just words sitting inside a chunk hoping to rank well?"*
- **Our Answer:**  
  *"It is a hard programmatic filter. In `data/policy_corpus.py` and `capstone_agent.py`, the active policy version is set to `HR-LEAVE-2025-v2.0` (Effective 2025-01-01). The 2024 policy chunks are excluded by metadata filtering unless the query explicitly contains historical temporal tokens (`2024`, `last year`, `prior policy`). Furthermore, an output regex validator asserts that both the version ID and effective date appear in the citation string; if absent, the response fails post-generation assertion."*

---

### Question 3: *"This thing reads employee records. Show me one raw log line from a real request. Not your redaction policy — a line. And tell me who on your team can read that log."*
- **Our Answer:**  
  *"Here is the exact line from `trace_example.json` emitted over our telemetry logger:*
  ```json
  {"trace_id":"tr-capstone-20261012-094522-8f1b3c","employee_id":"EMP-IN-001","entity":"India","grade":"[REDACTED_PII]","base_salary":"[REDACTED_PII]","leave_balances":"[REDACTED_PII]","tenure_years":3.2,"latency_ms":18.2}
  ```
  *Who can read this log? The entire AI engineering squad and DevOps can read this log in CloudWatch because the PII line is held at the function return boundary inside `data/employees.py` → `sanitize_for_logging()`. Neither salary band, performance grade, nor remaining sick days are ever serialized to disk or stdout."*

---

### Question 4: *"If it gives an employee the wrong maternity-leave entitlement and they plan four months around it, who is on the hook — HR, or you? Show me the refusal path and the assertion that enforces it."*
- **Our Answer:**  
  *"The system has two protective fail-safes: First, every maternity leave assertion in `run_capstone_eval.py` (Cases TC-07 through TC-12) tests that statutory annexes beat general handbook terms with zero tolerance. Second, on any non-standard situation or discretionary leave request exceeding standard statutory caps, the system executes `escalate_to_hrbp()` creating a traceable ticket. The model is explicitly prevented from synthesizing discretionary answers, ensuring that non-statutory commitments remain 100% human HRBP decisions."*

---

### Question 5: *"Your judge agreed with your labels 100% of the time (or 87% in earlier drafts). You are not an employment lawyer and neither is your judge. Why should I take either of your numbers into a grievance meeting?"*
- **Our Answer:**  
  *"You should not take our judge into a grievance meeting — and you don't need to. Our judge does not interpret employment law. Our judge evaluates strict, verifiable deterministic facts: (1) Did the answer cite Clause 2.1 of the India Annex? (2) Did it state version HR-LEAVE-2025-v2.0? (3) Did it state effective date 2025-01-01? (4) Did it quote exactly 26 weeks? These are deterministic boolean regex assertions against HR's approved policy document. What defends you in a grievance meeting is that the system cited the exact text approved by your Legal and HR Counsel, with the version and effective date stamped on the record."*
