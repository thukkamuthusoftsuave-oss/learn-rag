# Support Drill Report

**Time-to-find**: 01:45 (1 minute, 45 seconds)

**The slice/filter that found it:**
Since the complaint was "it quoted the wrong notice period, maybe Tuesday" and I didn't have a trace ID or user ID, I ran a `grep` (full-text search) over the `output_response` field across all logs in the `logs/` directory for the string `"30 days"` (the wrong notice period) and `"notice period"`. 
I found `trace_84f92a.json` which perfectly matched the vague complaint. 

**Root Cause Found:**
Looking at the trace, the retrieved context IDs included `HR-102_manager_notice_superseded`. This means the vector database retrieved an old, superseded policy document instead of the active one. The prompt version was `v1.2_pre_effective_date_patch`, meaning the agent prompt didn't explicitly instruct the LLM to prioritize effective dates over generic text matches.

**Fix Applied (Prompt Version Bump):**
* **Version Bump:** `v1.2_pre_effective_date_patch` -> `v1.3_strict_effective_dates`
* **Canary Plan:** 
  1. Deploy `v1.3_strict_effective_dates` to 10% of traffic (London office only) for 2 hours.
  2. If the failure rate spikes or complaints arrive, instantly rollback traffic routing to `v1.2_pre_effective_date_patch` in the config map.
