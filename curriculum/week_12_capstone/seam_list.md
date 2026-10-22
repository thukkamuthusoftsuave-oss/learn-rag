<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Tuesday's Unedited Seam List

**Project:** Variant C · Policy Answer Desk (HR Policy Shared-Services)  
**Date:** Tuesday of Week 12  
**Status Key:**
- `[FIXED]`: Seam identified and resolved prior to evaluation run.
- `[ACCEPTED]`: Seam understood, bounded with circuit breaker/fallback, accepted for current release.
- `[RAN-OUT-OF-TIME]`: Known architectural limitation deferred to post-capstone roadmap.

---

### Seam 1: Substring Matcher in Colleague Leak Guardrail Caught Legitimate Query Words
- **Location:** `capstone_agent.py` → `_detect_adversarial_leak_attempt()`
- **Issue:** The security guardrail scanned for colleague names in the employee database using naive substring inclusion (`name.lower() in query.lower()`). When an India Grade 3 employee asked *"Can I take a leave advance against next month's casual leave?"*, the query substring `"advance"` matched colleague surname `"vance"` (Eleanor Vance, EMP-UK-001). The agent immediately refused legitimate self-service requests with an adversarial leak refusal.
- **Impact:** 14% false-positive refusal rate on legitimate payroll/leave advance queries.
- **Resolution:** `[FIXED]` — Replaced substring search with regex word boundaries `re.search(rf"\b{re.escape(name_part)}\b", query, re.IGNORECASE)` and excluded the requester's own first/last names from triggering the check.

---

### Seam 2: MCP Stdio Serialization Dropped Distributed Trace Context
- **Location:** `hr_policy_mcp_server.py` ↔ `capstone_agent.py` JSON-RPC transport
- **Issue:** When the ReAct agent dispatched tool calls over the Model Context Protocol (MCP) stdio pipe, the agent's active `trace_id` was not passed in standard tool input schemas (`get_employee_record(emp_id="EMP-IN-001")`). The MCP server generated independent trace IDs, breaking end-to-end request tracing across the agent-to-tool seam.
- **Impact:** Distributed tracing failed; spans could not be correlated across the agent loop and MCP tool invocations.
- **Resolution:** `[FIXED]` — Injected optional `_trace_id` and `_parent_span_id` kwargs into all MCP tool definitions and agent invocation signatures. If passed, the MCP server binds to the existing trace tree; if absent, it starts a child trace.

---

### Seam 3: Hybrid Search BM25 Ranked General Handbook Above Entity Annex for Statutory Leave
- **Location:** `data/policy_corpus.py` → `search_policy_docs()`
- **Issue:** In the employee handbook, Section 4.1 contains extensive descriptive keywords (*"Maternity leave entitlement, 12 weeks basic salary, HR approval, statutory notice"*). The India Entity Annex Clause 2.1 is shorter and terse (*"Section 4.1 overridden: Maternity benefit is 26 weeks paid leave per Maternity Benefit Act"*). BM25 term frequency scored the 40-page general handbook higher than the terse statutory annex, causing India Grade 3 employees to be quoted 12 weeks instead of 26 weeks.
- **Impact:** 32% error rate on jurisdiction-specific statutory queries.
- **Resolution:** `[FIXED]` — Enforced deterministic precedence: policy search queries now mandatory-filter or prioritize `entity_scope == employee.entity`. When an entity annex clause exists for a section, the agent's synthesis engine enforces silent annex dominance (`India/UK Annex overrides General Handbook where conflicting`).

---

### Seam 4: Temporal Version Ambiguity in Default Policy Search
- **Location:** `capstone_agent.py` ↔ `data/policy_corpus.py`
- **Issue:** When employees asked general leave entitlement questions (*"How many days of privilege leave do I get?"*), both `HR-LEAVE-2024-v1.0` (15 days) and `HR-LEAVE-2025-v2.0` (18 days) returned high cosine similarity. Without explicit temporal filtering, the agent frequently synthesized answers blending clauses from both versions or citing the 2024 superseded policy as current.
- **Impact:** 26% superseded-version citation rate.
- **Resolution:** `[FIXED]` — Enforced active policy version filtering by default (`HR-LEAVE-2025-v2.0`, Effective 2025-01-01). The 2024 policy is retrieved only when the query explicitly specifies a historical retrospective timeframe (*"in 2024"*, *"prior policy"*, *"last year"*). Every citation must explicitly output version ID and effective date.

---

### Seam 5: Discretionary Leave Inquiries Generated Speculative LLM Answers
- **Location:** `capstone_agent.py` synthesis prompt
- **Issue:** When employees asked about discretionary exceptions (*"Can I take 10 days compassionate leave for an uncle?"* or *"Can a Grade 7 employee negotiate 6 months unpaid sabbatical?"*), the LLM generated plausible-sounding advice (*"You can apply and your manager might grant 7 days..."*). In HR shared services, discretionary guessing leads directly to employment grievances.
- **Impact:** Hallucinated company commitments on non-statutory benefits.
- **Resolution:** `[FIXED]` — Implemented hard routing rules for discretionary scenarios: Compassionate leave >5 days, Sabbatical tenure split exceptions, Grade 7 executive customized notice, and negative leave advances automatically invoke `escalate_to_hrbp` with ticket generation and refusal to guess.

---

### Seam 6: Asynchronous MCP Tool Latency Spikes Under SQLite File Locks
- **Location:** `hr_policy_mcp_server.py` database reader
- **Issue:** Concurrent queries attempting to read employee records during simulated peak load experienced 1.8s latency spikes when SQLite experienced write locks on escalation ticket creation.
- **Impact:** High p99 latency during multi-turn evals.
- **Resolution:** `[ACCEPTED]` — Wrapped SQLite operations in WAL mode (`PRAGMA journal_mode=WAL;`) and added an in-memory cached fallback dictionary for read-only employee metadata with a 2.5s timeout circuit breaker.

---

### Seam 7: Raw PDF Table Chunking Loses Grade-Band Column Hierarchy
- **Location:** `curriculum/week_12_capstone/data/policy_corpus.py`
- **Issue:** Chunks extracted directly from markdown-converted PDF tables for Grade Matrix (Grades 1–7 across Annual Leave, Notice, Sabbatical) lost column alignment when chunked with a naive 500-token window, splitting Grade 3 and Grade 4 across chunk boundaries.
- **Impact:** 18% error rate when mapping Grade 4 notice periods.
- **Resolution:** `[RAN-OUT-OF-TIME]` — Retained structured JSON schema indexing for the Grade-Band matrix rather than relying on raw unparsed document table chunks. Structured retrieval passes exact grade rows directly to the agent context.
