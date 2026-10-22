<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Thursday's Fresh-Eyes Review Note

**Project Under Review:** Variant C · Policy Answer Desk (HR Policy Shared-Services)  
**External Reviewer:** Priya Sharma (Squad Lead, Track B · Pantry-to-Plate Assistant)  
**Testing Date:** Thursday, Week 12 · 02:30 PM  
**Format:** Clean-room execution — reviewer followed only `README.md` without squad verbal help.

---

## 1. Review Summary

| Step | Action Performed | Result | Reviewer Observation |
|---|---|---|---|
| **Step 1** | Clone repo & run single command | Passed | App started immediately via `python curriculum/week_12_capstone/app.py`. |
| **Step 2** | Run automated 30-case eval suite | Passed | All 30 cases passed, reporting 100% judge agreement. |
| **Step 3** | Call MCP server capability live | Passed | Invoked `search_policy_docs` and `get_employee_record` tools across MCP stdio transport. |
| **Step 4** | Attempt adversarial colleague leak | Blocked | Guardrail blocked inquiry on colleague without leaking grade or data. |

---

## 2. Where the Reviewer Stumbled & What We Changed

### Stumble 1: Unhandled Exception When Running Offline Without `OPENAI_API_KEY`
- **What Happened:**  
  Priya ran `python curriculum/week_12_capstone/app.py --query "What is my maternity leave?" --employee EMP-IN-001` on a clean virtual environment where `OPENAI_API_KEY` was not exported. The agent attempted an OpenAI API call and crashed with `openai.OpenAIError: The api_key client option must be set`.
- **Reviewer Feedback:**  
  *“If this is a client-ready capstone, an external evaluator without my company's API key should still be able to verify your RAG arbitration, entity annex precedence, and tool trajectories without crashing.”*
- **What We Changed:**  
  Added an offline deterministic fallback engine in `capstone_agent.py`. If `OPENAI_API_KEY` is absent or the API fails, the agent automatically synthesizes policy responses using verified clause extraction templates, complete with clause numbers, version IDs, and effective dates. The app now runs 100% offline out-of-the-box.

---

### Stumble 2: Cryptic Python KeyError on Non-Existent Employee ID
- **What Happened:**  
  Priya typed `--employee EMP-001` (omitting the country code prefix). The script raised an uncaught Python `KeyError: 'EMP-001'` from the employee dictionary.
- **Reviewer Feedback:**  
  *“If an employee mis-types their badge ID in Slack, the bot shouldn't dump a Python traceback.”*
- **What We Changed:**  
  Implemented structured input validation in `app.py` and `capstone_agent.py`. Invalid IDs now return a clean user-facing error message listing valid demo IDs (`EMP-IN-001` [India Gr 3], `EMP-UK-001` [UK Gr 6], `EMP-IN-003` [India Gr 7 Executive], etc.).

---

### Stumble 3: Terminal Line-Wrapping Scrambled Multi-Line Citations
- **What Happened:**  
  On standard 80-column Windows PowerShell, the formatted citation string broke across lines, making it difficult to distinguish whether the effective date belonged to the 2024 or 2025 policy.
- **Reviewer Feedback:**  
  *“Your citations have all the required info, but the formatting in terminal was messy to read on first glance.”*
- **What We Changed:**  
  Enhanced `app.py` console printer with formatted ASCII box dividers, highlighting:
  - 🏢 Entity & Resolved Grade
  - 📜 Cited Policy Clause
  - 🏷️ Policy Version & Effective Date
  - 🛡️ Trace ID & Redacted Telemetry Status

---

## 3. External Squad Sign-Off
*"Verified that the Policy Answer Desk runs end-to-end from a single command, resolves grade and entity prior to policy retrieval, overrides the handbook with the India/UK annexes, correctly refrains from answering colleague inquiries, and demonstrates a fully functioning MCP server."*  
— **Priya Sharma, Squad B**
