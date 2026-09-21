# Week 5: Error Analysis & Evaluation Taxonomy

## 1. Learning Objectives
- Formalize the closed **Error Taxonomy** for enterprise RAG systems.
- Calculate **Impact Scores** using the formula: $\text{Impact} = \text{Frequency} \times \text{Severity}$.
- Generate actionable **Prediction Cards** identifying the highest-leverage architectural fix.
- Contrast automated evaluation with human review using golden evaluation sheets.

---

## 2. Theoretical Background

### The Five Error Classes
1. **`CORRECT`** (Severity 0): Expected document in top-3, factual answer matching ground truth.
2. **`CORRECT_REFUSAL`** (Severity 0): Expected out-of-domain query refused with canonical phrase.
3. **`GENERATION_FAILURE`** (Severity 3): Ground truth document retrieved, but LLM misread table, hallucinated facts, or refused unnecessarily.
4. **`RETRIEVAL_FAILURE`** (Severity 4): Target document omitted from top-3 context, causing wrong-region hallucination or forced refusal.
5. **`PIPELINE_ERROR`** (Severity 5): Network failure, rate limit exception, or vector store timeout.

### The Prediction Card Pattern
Engineering teams frequently waste time debating speculative fixes. The Prediction Card pattern forces a disciplined decision:
- **One Problem**: The top-ranked issue by Impact Score.
- **One Action**: The exact architectural change to test.
- **Expected Improvement**: The concrete metrics that will move.
- **Explicit Non-Goal**: The failure modes the change will **not** fix (preventing false expectations).

---

## 3. Code Architecture

- [`error_taxonomy.py`](file:///d:/learn-rag/curriculum/week_05_error_analysis_and_eval_taxonomy/error_taxonomy.py): Formal label definitions, severity mappings, and impact ranking.
- [`prediction_card.py`](file:///d:/learn-rag/curriculum/week_05_error_analysis_and_eval_taxonomy/prediction_card.py): Algorithmic synthesis of ranked errors into a standardized executive prediction card.
- [`run_eval.py`](file:///d:/learn-rag/curriculum/week_05_error_analysis_and_eval_taxonomy/run_eval.py): Demonstration of trace ingestion, impact calculation, and prediction card output.

---

## 4. How to Run

```powershell
python curriculum/week_05_error_analysis_and_eval_taxonomy/run_eval.py
```
