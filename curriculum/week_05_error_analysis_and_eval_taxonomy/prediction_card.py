"""Week 5: Actionable Prediction Card Generator.

Synthesizes ranked errors into a clear, single-action prediction card
specifying what engineering change to make next, what metric it will improve,
and what problem it will NOT fix.
"""

from typing import List, Dict, Any


def generate_prediction_card(ranked_issues: List[Dict[str, Any]]) -> str:
    """Generates an executive prediction card from the highest-impact error."""
    top_issues = [i for i in ranked_issues if i["severity"] > 0]
    if not top_issues:
        return "### Prediction Card: All Evaluated Traces Clean (Pass Rate 100%). No remediation needed."

    primary_issue = top_issues[0]
    label = primary_issue["label"]

    if label == "RETRIEVAL_FAILURE":
        action = "Enable Hybrid Retrieval (BM25 + BGE Vector via Reciprocal Rank Fusion) and Region Filters"
        will_move = "Hit-Rate@1 and Hit-Rate@3 on exact-term, numerical threshold, and section-number queries."
        will_not_fix = "Generation hallucinations or prompt over-refusals where the document is already in top 3."
    elif label == "GENERATION_FAILURE":
        action = "Add Cross-Encoder Reranker (bge-reranker-base) or tighten system prompt refusal rules"
        will_move = "Answer accuracy when correct document is present in candidate pool."
        will_not_fix = "Retrieval omissions where the target document was missed entirely by top-k."
    else:
        action = "Implement retry policies with exponential backoff and quota monitoring"
        will_move = "Pipeline availability and error rates."
        will_not_fix = "Underlying semantic retrieval quality."

    card = f"""
================================================================================
                    RAG OPTIMIZATION PREDICTION CARD
================================================================================
Top Problem Identified : {label} (Impact Score: {primary_issue['impact_score']} | Count: {primary_issue['count']})
Recommended Action     : {action}
Expected Improvement   : {will_move}
Explicit Non-Goal      : {will_not_fix}
Remediation Guidance   : {primary_issue['remediation']}
================================================================================
"""
    return card
