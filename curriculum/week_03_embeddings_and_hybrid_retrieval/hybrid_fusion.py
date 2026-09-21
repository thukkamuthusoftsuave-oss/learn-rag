"""Week 3: Reciprocal Rank Fusion (RRF) Hybrid Retriever.

Fuses ranked results from Dense Vector search and Sparse BM25 search
using the standard RRF formula: RRF_Score(d) = sum(1 / (k + rank)).
"""

from typing import List, Dict, Any


def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    rrf_k: int = 60,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Fuses vector and BM25 ranked lists using Reciprocal Rank Fusion.
    
    Formula:
        RRF_Score(doc) = sum_{retriever} [ 1 / (rrf_k + rank) ]
    """
    scores: Dict[str, float] = {}
    doc_lookup: Dict[str, Dict[str, Any]] = {}

    # Score vector rankings (1-indexed rank)
    for rank, doc in enumerate(vector_results, start=1):
        doc_id = doc.get("chunk_id") or doc.get("section")
        scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank))
        if doc_id not in doc_lookup:
            doc_lookup[doc_id] = doc

    # Score BM25 rankings (1-indexed rank)
    for rank, doc in enumerate(bm25_results, start=1):
        doc_id = doc.get("chunk_id") or doc.get("section")
        scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank))
        if doc_id not in doc_lookup:
            doc_lookup[doc_id] = doc

    # Sort descending by fused RRF score
    sorted_doc_ids = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)[:top_k]
    
    fused_results = []
    for rank, doc_id in enumerate(sorted_doc_ids, start=1):
        doc = dict(doc_lookup[doc_id])
        doc["rrf_score"] = scores[doc_id]
        doc["fused_rank"] = rank
        fused_results.append(doc)

    return fused_results
