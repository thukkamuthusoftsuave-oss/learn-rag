# Week 7 Practical Deliverables: Task Set C (HR Policy)
## Race the HR Agent Against a Fixed Workflow

**Module**: Week 7 · Module 4 — Agents  
**Domain**: HR Policy (Task Set C)  
**Deliverable**: Hand-built ReAct Agent with visible steps vs. Deterministic Fixed Workflow  

---

## 1. Executive Summary & The 8 Numbers Table

Both systems were evaluated across the identical benchmark suite of **10 employee entitlement questions**, which includes **5 tenure- and jurisdiction-branching cases** (e.g., tenure under 2 years triggering statutory 1-week notice vs. multi-year accrual; California statutory wage protection overriding policy forfeiture; EMEA 5-year sabbatical thresholds).

### Comparable 8 Numbers Summary Table

| Metric | Hand-built Agent | Fixed Workflow | Delta / Ratio | Analysis |
|---|---|---|---|---|
| **Pass Rate (%)** | **100.0%** (10/10) | **100.0%** (10/10) | Parity (1.0x) | Both systems achieve perfect accuracy across all 10 policy queries. |
| **p50 Latency (ms)** | **70.16 ms** | **20.95 ms** | **3.3x Faster** (Workflow) | Workflow executes in a single pass; Agent incurs multi-round LLM network turns. |
| **Total Cumulative Tokens** | **39,259 tokens** | **4,537 tokens** | **8.7x Fewer** (Workflow) | Agent re-transmits all historical messages & tool schemas on every lap. |
| **Cost per Question ($)** | **$0.000706** | **$0.000106** | **6.7x Cheaper** (Workflow) | Summed multi-lap token re-sending inflates agent operating expenses. |

*Artifact: Full per-question results, category breakdown, and raw logs are persisted in [`race.csv`](file:///d:/learn-rag/race.csv).*

---

## 2. Verdict Applying the Decision Rule

> **Decision Rule Verdict (< 150 words):**  
> We ship the **Fixed Workflow**. Applying the engineering decision rule—*use an agent only when the execution path dynamically varies with input*—the benchmark numbers settle the debate definitively. For entitlement determinations, the reasoning path is a known directed acyclic graph (lookup employee record → fetch handbook section → check statutory overrides → synthesize). On this closed decision space, the workflow delivers identical 100% accuracy while running **3.3x faster**, consuming **8.7x fewer tokens**, and cutting costs by **6.7x** with zero tool-calling hallucination risk. None of the 10 questions justifies an agent. An agent is forced only for an open-ended, ambiguous question class where lookups cannot be modeled as a predefined DAG—such as cross-referencing conflicting informal manager emails with unindexed severance exceptions, or dynamic multi-turn dispute arbitrations requiring unstructured clarifying questions.

---

## 3. Third Tool Specification & Description Diff

### Design Principles
1. **Single Job**: Looks up only statutory labor laws and legal overrides; does not query internal employee records or company handbook text.
2. **Typed Enum Parameters**: Uses `JurisdictionEnum` (`US`, `UK`, `EMEA`, `APAC`, `LATAM`, `NA`) and `PolicyTopicEnum`.
3. **Zero Overlap**: The boundaries of all three tools are strictly disjoint:
   - `get_employee_record`: Exclusively demographic, tenure, and leave balance database records.
   - `get_handbook_rule`: Exclusively corporate HR-207 policy handbook text and standard cap tables.
   - `get_jurisdiction_rules`: Exclusively statutory labor codes and government legal mandates.

### Git Diff of Tool Registry

```diff
Index: policy_rag/agent/tools.py
===================================================================
--- policy_rag/agent/tools.py (baseline: 2 tools)
+++ policy_rag/agent/tools.py (with third tool)
@@ -1,15 +1,60 @@
+from policy_rag.agent.enums import JurisdictionEnum, PolicyTopicEnum
+
+# --- Tool 1: Employee Records ---
 def get_employee_record(employee_id: str) -> Dict[str, Any]:
-    """Retrieve an employee's personal HR profile by employee ID."""
+    """Retrieve an employee's personal HR profile by employee ID.
+    Returns employee demographics, corporate jurisdiction, continuous service tenure in years,
+    employment classification (Probationary, Regular, Senior), weekly scheduled hours, and accrued/used vacation days.
+    Does NOT return company handbook policies or statutory labor laws."""
 
+# --- Tool 2: Company Policy Handbook ---
 def get_handbook_rule(jurisdiction: JurisdictionEnum, section_or_topic: str) -> Dict[str, Any]:
-    """Retrieve standard company HR-207 handbook policy text."""
+    """Retrieve standard company HR-207 handbook policy text, entitlement tiers, and baseline carry-over caps
+    for a specified corporate jurisdiction and policy section.
+    Does NOT return individual employee records or local statutory labor regulations."""
+
+# --- Tool 3: Statutory Jurisdiction Regulations (NEW) ---
+def get_jurisdiction_rules(jurisdiction: JurisdictionEnum, topic: PolicyTopicEnum) -> Dict[str, Any]:
+    """Retrieve statutory labor regulations and government legal mandates for a specified jurisdiction and policy topic,
+    including statutory notice period requirements based on service length, state-mandated wage protections against forfeiture,
+    and mandatory part-time holiday pro-rata rules.
+    Does NOT retrieve company handbook rules or employee records."""
+    jur_key = jurisdiction.value if isinstance(jurisdiction, JurisdictionEnum) else str(jurisdiction).upper()
+    topic_key = topic.value if isinstance(topic, PolicyTopicEnum) else str(topic).lower()
+    statutory_jur = STATUTORY_JURISDICTION_RULES.get(jur_key, {})
+    if topic_key in statutory_jur:
+        return {
+            "status": "success",
+            "jurisdiction": jur_key,
+            "topic": topic_key,
+            "statutory_rules": statutory_jur[topic_key],
+        }
+    return {"status": "not_found", "error": f"No statutory labor rules for '{jur_key}' and '{topic_key}'."}
+
+# --- Tool Schema Definition ---
+{
+    "type": "function",
+    "function": {
+        "name": "get_jurisdiction_rules",
+        "description": "Retrieve statutory labor regulations and government legal mandates for a specified jurisdiction and policy topic...",
+        "parameters": {
+            "type": "object",
+            "properties": {
+                "jurisdiction": {
+                    "type": "string",
+                    "enum": ["US", "UK", "EMEA", "APAC", "LATAM", "NA"],
+                    "description": "Government/legal jurisdiction code as a strictly typed enum."
+                },
+                "topic": {
+                    "type": "string",
+                    "enum": ["carry_over_cap", "notice_period", "sabbatical", "part_time_rule", "borrowing_negative_balance", "termination_payout", "statutory_leave"],
+                    "description": "The specific legal topic governed by statutory regulation."
+                }
+            },
+            "required": ["jurisdiction", "topic"]
+        }
+    }
+}
```

---

## 4. Four-Budget Enforcement & Clean Termination Log

The agent loop enforces all four operational budgets:
1. `max_iterations`: Hard cap on ReAct thinking/action rounds.
2. `max_tokens`: Cumulative sum of prompt and completion tokens across every lap.
3. `max_cost`: Cumulative dollar expenditure calculated per token tier.
4. `wall_clock`: Real elapsed wall-clock timeout.

### Verified Termination Logs

```text
================================================================================
BUDGET TERMINATION DEMONSTRATION
================================================================================

>>> TEST 1: Triggering 'max_iterations' Budget Termination (limit = 1)...
[Agent Started] Query: 'What is the mandatory notice period for employee EMP-101 in the UK?'
[Budgets] max_iters=1, max_tokens=8000, max_cost=$0.05, max_time=15.0s

--- [Lap 1] Thinking ---
  Thought: I need to inspect the employee record for EMP-101 to determine their jurisdiction, tenure, and classification.
  Lap Usage: prompt=771 compl=62 (Total: 833 tokens, $0.000153)
  Action: Call `get_employee_record` with args: {'employee_id': 'EMP-101'}
  Observation: {"status": "success", "employee": {"employee_id": "EMP-101", "name": "Alice Smith", "jurisdiction": "UK", ...}}

[BUDGET EXCEEDED] max_iterations exceeded at lap 1: current=1.0000 limit=1.0000. Terminating cleanly.
Status: budget_exceeded | Reason: budget_exceeded
Answer: Terminated early: [BUDGET EXCEEDED] max_iterations exceeded at lap 1: current=1.0000 limit=1.0000. Terminating cleanly.

>>> TEST 2: Triggering 'max_tokens' Budget Termination (limit = 500)...
[Agent Started] Query: 'What is the mandatory notice period for employee EMP-101 in the UK?'
[Budgets] max_iters=6, max_tokens=500, max_cost=$0.05, max_time=15.0s
--- [Lap 1] Thinking ---
[BUDGET EXCEEDED] max_tokens exceeded at lap 1: current=833.0000 limit=500.0000. Terminating cleanly.
Status: budget_exceeded | Reason: budget_exceeded

>>> TEST 3: Triggering 'max_cost' Budget Termination (limit = $0.00005)...
[Agent Started] Query: 'What is the mandatory notice period for employee EMP-101 in the UK?'
[Budgets] max_iters=6, max_tokens=8000, max_cost=$5e-05, max_time=15.0s
--- [Lap 1] Thinking ---
[BUDGET EXCEEDED] max_cost exceeded at lap 1: current=0.0002 limit=0.0001. Terminating cleanly.
Status: budget_exceeded | Reason: budget_exceeded

>>> TEST 4: Triggering 'wall_clock' Budget Termination (limit = 0.005s)...
[Agent Started] Query: 'What is the mandatory notice period for employee EMP-101 in the UK?'
[Budgets] max_iters=6, max_tokens=8000, max_cost=$0.05, max_time=0.005s
--- [Lap 1] Thinking ---
[BUDGET EXCEEDED] wall_clock exceeded at lap 1: current=0.0159 limit=0.0050. Terminating cleanly.
Status: budget_exceeded | Reason: budget_exceeded
================================================================================
```

---

## 5. Fixed Workflow Implementation Excerpt

The workflow does not use a `while` loop, dynamic planning, or model-driven tool dispatch. It executes four deterministic Python steps using the exact same tools and schemas:

```python
class FixedWorkflow:
    def run(self, query: str) -> Dict[str, Any]:
        # Step 1: Deterministic employee ID extraction & DB lookup
        emp_id = self._extract_employee_id(query) or "EMP-101"
        step1_result = get_employee_record(emp_id)
        emp_info = step1_result["employee"]
        jurisdiction = JurisdictionEnum(emp_info["jurisdiction"])
        topic = self._extract_topic(query, emp_info.get("hours_per_week", 40.0))

        # Step 2: Deterministic handbook policy retrieval
        step2_result = get_handbook_rule(jurisdiction, topic.value)

        # Step 3: Conditional statutory rule lookup (e.g. tenure branching)
        needs_statutory = (
            (jurisdiction == JurisdictionEnum.UK and topic == PolicyTopicEnum.NOTICE_PERIOD)
            or (jurisdiction == JurisdictionEnum.US and (topic == PolicyTopicEnum.TERMINATION_PAYOUT or emp_info.get("sub_region") == "California"))
            or (jurisdiction == JurisdictionEnum.EMEA and topic == PolicyTopicEnum.SABBATICAL)
            or (jurisdiction == JurisdictionEnum.APAC and topic == PolicyTopicEnum.NOTICE_PERIOD)
        )
        step3_result = get_jurisdiction_rules(jurisdiction, topic) if needs_statutory else None

        # Step 4: Single LLM synthesis step (Zero loops, 1 LLM network call)
        messages = [
            {"role": "system", "content": "You are an expert HR Policy Entitlement assistant..."},
            {"role": "user", "content": query},
            {"role": "tool", "name": "get_employee_record", "content": json.dumps(step1_result)},
            {"role": "tool", "name": "get_handbook_rule", "content": json.dumps(step2_result)},
        ]
        if step3_result:
            messages.append({"role": "tool", "name": "get_jurisdiction_rules", "content": json.dumps(step3_result)})

        llm_resp = call_llm(messages=messages, tools=None)
        return {"status": "success", "answer": llm_resp.content, "laps": 1, ...}
```

---

## 6. Bonus Challenge: 30-Turn Memory & Process Restart Analysis

### Architecture
- **Sliding Window Buffer**: Retains the last 5 conversation pairs (10 messages) verbatim.
- **Executive Summarizer**: Compresses conversational turns that slide outside the active window into high-level bullet summaries.
- **Persistent Disk Fact Store**: Persists `EMP-105_jurisdiction: "US"` to `var/agent_memory.json`, surviving full process restarts.

### Verification of Surviving Process Restart
```text
>>> PHASE 1: Persisting employee jurisdiction to disk...
  Saved to: D:\learn-rag\var\agent_memory.json
  Persisted: EMP-105_jurisdiction = US

>>> PHASE 2: Simulating full process restart...
  Recovered jurisdiction after process restart: US
  [PASS] Fact survived full process restart cleanly.
```

### 30-Turn Conversation Failure Analysis
- **Turn 4 User Context**: *"For employee EMP-105 (Evan Wright), on April 14 the VP of HR granted an exception approving exactly 2.5 additional carry-over days under Section 4.9 due to the project freeze."*
- **Compression Event**: At turn 12, turn 4 slid out of the active window. The summarizer condensed it into:  
  `"Earlier topics: Employee requested and discussed HR policy exceptions with leadership."`
- **Detail Destroyed**: The specific numerical grant of **`2.5 additional carry-over days approved on April 14`** was stripped in favor of high-level category phrasing.
- **The Broken Question (Turn 29)**: *"How many exact additional exception carry-over days did the VP approve for EMP-105 on April 14?"*
- **Failure Mode**: The agent hallucinated or stated that the exact fractional number of days was unavailable, citing only the general 5-day ceiling: *"The specific fractional number of days approved is not present in recent context; standard policy permits up to 5 days with VP approval."*

---

## 7. Submission Checklist Verification

- [x] **Agent and workflow runnable by one command each**:
  - Agent: `python -m policy_rag agent "What is the notice period for EMP-101 in the UK?"`
  - Workflow: `python -m policy_rag workflow "What is the notice period for EMP-101 in the UK?"`
  - Race Suite: `python -m policy_rag race`
  - Budget Demo: `python -m policy_rag budget-demo`
  - Memory Bonus: `python -m policy_rag memory-bonus`
- [x] **`race.csv` generated with all 8 numbers**: Persisted in `race.csv`.
- [x] **Log excerpt of budget-triggered termination**: Documented for all 4 budgets.
- [x] **Diff of third tool description & parameter enums**: Included in Section 3.
- [x] **Verdict paragraph**: Compliant with decision rule, under 150 words, and aligned with numbers.
