"""Week 4: Failure Separation Engine (Retrieval Failure vs Generation Failure).

Implements the fundamental engineering decision test:
Separating errors caused by the retriever from errors caused by the generator.
"""

from typing import List, Dict, Any, Optional

REFUSAL_CANONICAL = "I cannot answer this question based on the provided HR-207 policy addenda."


def classify_pipeline_outcome(
    query: str,
    answer: str,
    retrieved_sources: List[str],
    expected_source: Optional[str],
    expected_type: str = "answer",
) -> Dict[str, Any]:
    """Classifies a RAG output into Retrieval Failure, Generation Failure, or Success.
    
    Decision Rules:
    1. expected_type == "refusal":
       - answer matches refusal -> CORRECT_REFUSAL
       - answer hallucinates -> GENERATION_FAILURE
    2. expected_type == "answer":
       - answer matches refusal:
           - expected_source in top-3 sources -> GENERATION_FAILURE (over-refusal)
           - expected_source NOT in top-3 -> RETRIEVAL_FAILURE (retriever failed)
       - answer provided:
           - expected_source in top-3 sources -> CORRECT (or GENERATION_FAILURE if factually wrong)
           - expected_source NOT in top-3 -> RETRIEVAL_FAILURE (answered from wrong doc)
    """
    is_refusal = REFUSAL_CANONICAL.lower() in answer.lower() or "cannot answer" in answer.lower()
    top_3_sources = retrieved_sources[:3]
    retrieval_ok = (expected_source is None) or (expected_source in top_3_sources)

    if expected_type == "refusal":
        if is_refusal:
            label = "CORRECT_REFUSAL"
            diagnosis = "Correctly refused out-of-corpus query."
        else:
            label = "GENERATION_FAILURE"
            diagnosis = "Hallucination: answered an out-of-corpus query that should have been refused."
    else:
        if is_refusal:
            if retrieval_ok:
                label = "GENERATION_FAILURE"
                diagnosis = "Over-eager refusal: document was in context but LLM refused anyway."
            else:
                label = "RETRIEVAL_FAILURE"
                diagnosis = "Retriever failed to supply the expected document, forcing a refusal."
        else:
            if retrieval_ok:
                label = "CORRECT"
                diagnosis = "Retrieved correct document and synthesized an answer."
            else:
                label = "RETRIEVAL_FAILURE"
                diagnosis = "Confidently wrong: answered from the wrong document/jurisdiction."

    return {
        "query": query,
        "label": label,
        "diagnosis": diagnosis,
        "retrieval_ok": retrieval_ok,
        "is_refusal": is_refusal,
        "top_sources": top_3_sources,
        "expected_source": expected_source
    }
