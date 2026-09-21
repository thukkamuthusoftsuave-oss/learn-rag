# Week 4: Retrieval Debugging & Failure Separation

## 1. Learning Objectives
- Learn the foundational engineering principle of RAG debugging: **Failure Separation**.
- Categorize errors into **Retrieval Failures** vs. **Generation Failures**.
- Design deterministic **Prompt Guardrails** for out-of-domain questions to eliminate hallucinations.
- Understand why upgrading an LLM does not resolve retrieval failures.

---

## 2. Theoretical Background

### The Two Types of Wrong
A RAG system produces bad answers for two completely different reasons:
1. **Retrieval Failure**: The required document was never retrieved into the context window.
   - *Consequence*: The LLM either hallucinates from parametric memory or triggers refusal.
   - *Fix*: BM25, hybrid search, metadata filtering, chunk resizing, or query rewriting.
   - *Trap*: Swapping to a more powerful LLM (e.g. GPT-4o or Claude 3.5 Sonnet) fixes **zero** retrieval failures because the factual source is missing from the prompt.
2. **Generation Failure**: The document was retrieved in the top 3 chunks, but the LLM still failed.
   - *Consequence*: The LLM misread an eligibility table, missed an exception clause, hallucinated ungrounded numbers, or refused when it should have answered.
   - *Fix*: Prompt engineering, few-shot examples, cross-encoder reranking (placing key facts at the top of context), or upgrading model capability.

### Deterministic Refusal
When a user asks about topics absent from the corpus (e.g., maternity leave in HR-207 when HR-207 only governs PTO and sabbaticals), the prompt must mandate an exact refusal phrase. A polite guess is treated as a severe security and compliance vulnerability.

---

## 3. Code Architecture

- [`failure_separator.py`](file:///d:/learn-rag/curriculum/week_04_retrieval_debugging_and_failure_separation/failure_separator.py): The decision classifier evaluating if an error stems from retrieval or generation.
- [`refusal_engine.py`](file:///d:/learn-rag/curriculum/week_04_retrieval_debugging_and_failure_separation/refusal_engine.py): System prompt and context assembler enforcing canonical refusal behavior.
- [`run_eval.py`](file:///d:/learn-rag/curriculum/week_04_retrieval_debugging_and_failure_separation/run_eval.py): Unit test cases demonstrating the four failure separation modes.

---

## 4. How to Run

```powershell
python curriculum/week_04_retrieval_debugging_and_failure_separation/run_eval.py
```
