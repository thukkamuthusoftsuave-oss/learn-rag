"""Week 5: Error Taxonomy & Severity Ranking.

Defines the closed set of error labels, severity scores, and ranking logic
used to diagnose production RAG quality.
"""

from typing import List, Dict, Any

SEVERITY_MAP = {
    "CORRECT": 0,
    "CORRECT_REFUSAL": 0,
    "UNLABELED": 0,
    "GENERATION_FAILURE": 3,
    "RETRIEVAL_FAILURE": 4,
    "PIPELINE_ERROR": 5,
}

REMEDIATIONS = {
    "RETRIEVAL_FAILURE": (
        "Tune retriever: enable BM25 hybrid search, verify chunk boundary cohesion, "
        "or enforce exact-match metadata filters on region."
    ),
    "GENERATION_FAILURE": (
        "Tune synthesizer: add a cross-encoder reranker to surface key clauses to rank 1, "
        "or adjust prompt refusal thresholds."
    ),
    "PIPELINE_ERROR": (
        "Inspect system stability, API quotas, network connectivity, and store availability."
    ),
}


def rank_issues_by_impact(classified_traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ranks observed error categories by Frequency * Severity."""
    counts: Dict[str, int] = {}
    examples: Dict[str, List[str]] = {}

    for t in classified_traces:
        lbl = t.get("label", "UNLABELED")
        counts[lbl] = counts.get(lbl, 0) + 1
        if lbl not in examples:
            examples[lbl] = []
        if len(examples[lbl]) < 3:
            examples[lbl].append(t.get("query", ""))

    ranked = []
    for label, count in counts.items():
        severity = SEVERITY_MAP.get(label, 0)
        impact = count * severity
        ranked.append({
            "label": label,
            "count": count,
            "severity": severity,
            "impact_score": impact,
            "remediation": REMEDIATIONS.get(label, "No action required."),
            "examples": examples.get(label, [])
        })

    # Sort descending by impact score
    return sorted(ranked, key=lambda x: x["impact_score"], reverse=True)
