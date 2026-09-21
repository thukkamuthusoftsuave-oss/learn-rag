# Week 6: Advanced RAG, Multi-Turn Chat & Query Condensation

## 1. Learning Objectives
- Implement **Contextual Query Condensation** to rewrite conversational follow-ups into standalone retrieval queries.
- Track conversational state across multiple turns with a **Session Manager**.
- Enforce strict **Citation Grounding** (`[[HR-207 Section X.Y]]`) with automated citation verification.

---

## 2. Theoretical Background

### The Multi-Turn Follow-Up Problem
In production chat interfaces, users naturally communicate with anaphoric pronouns and ellipsis:
- *User*: "What is the carry-over cap for a regular employee in the US?"
- *Assistant*: "It is 10 days under Section 4.2."
- *User*: "What about the UK?"

If the second turn is passed directly to vector search, the retriever queries `"What about the UK?"`, which matches general country headers rather than carry-over policies.

**Query Condensation** inspects the conversation history and rewrites the query into:
`"What is the carry-over cap for a regular employee in the UK?"` before touching the vector database.

### Citation Verification
To prevent ungrounded claims, answers must wrap section references in double brackets `[[HR-207 Section X.Y]]`. The response parser checks that each cited section was actually present in the retrieved context.

---

## 3. Code Architecture

- [`condensation_engine.py`](file:///d:/learn-rag/curriculum/week_06_advanced_rag_multiturn_and_query_condensation/condensation_engine.py): Rewrites conversational follow-ups into standalone queries.
- [`session_manager.py`](file:///d:/learn-rag/curriculum/week_06_advanced_rag_multiturn_and_query_condensation/session_manager.py): Multi-turn session state management.
- [`citation_synthesizer.py`](file:///d:/learn-rag/curriculum/week_06_advanced_rag_multiturn_and_query_condensation/citation_synthesizer.py): Regex citation extractor and validator.
- [`run_eval.py`](file:///d:/learn-rag/curriculum/week_06_advanced_rag_multiturn_and_query_condensation/run_eval.py): Interactive demonstration of query condensation and citation verification.

---

## 4. How to Run

```powershell
python curriculum/week_06_advanced_rag_multiturn_and_query_condensation/run_eval.py
```
