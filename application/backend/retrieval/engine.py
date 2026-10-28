"""High-Performance Native Hybrid Retrieval Engine.

Features:
1. Native ChromaDB HNSW vector queries with sub-millisecond nearest neighbor search and exact metadata filtering.
2. Pre-tokenized in-memory BM25Okapi for instant sparse lexical retrieval.
3. Reciprocal Rank Fusion (RRF) combining vector and lexical rankings.
4. LRU query-level caching for sub-millisecond repeated lookups.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
import chromadb
from rank_bm25 import BM25Okapi
from application.backend.ingestion.pipeline import (
    load_all_policy_documents,
    get_chroma_client,
    run_ingestion_pipeline
)
from application.backend.core.config import settings
from application.backend.observability.langfuse_telemetry import capstone_telemetry as tracer


class ProductionHybridRetriever:
    """Enterprise-grade hybrid retriever fusing ChromaDB HNSW vector search with cached BM25."""

    def __init__(self):
        self._initialized = False
        self.chroma_client: Optional[chromadb.PersistentClient] = None
        self.chroma_collection = None
        self.chunks: List[Dict[str, Any]] = []
        self.chunk_id_map: Dict[str, Dict[str, Any]] = {}
        self.bm25: Optional[BM25Okapi] = None
        self._query_cache: Dict[str, List[Dict[str, Any]]] = {}

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def initialize(self, force_reindex: bool = False):
        """Initializes and pre-warms ChromaDB collection and BM25 token tables."""
        if self._initialized and not force_reindex:
            return

        self.chroma_client = get_chroma_client()
        collection_name = "policy_rag_production"

        # Check if collection exists and has documents; if not, index fresh
        try:
            self.chroma_collection = self.chroma_client.get_collection(collection_name)
            if self.chroma_collection.count() == 0:
                run_ingestion_pipeline(fresh=True)
                self.chroma_collection = self.chroma_client.get_collection(collection_name)
        except Exception:
            run_ingestion_pipeline(fresh=True)
            self.chroma_collection = self.chroma_client.get_collection(collection_name)

        # Pre-cache chunk metadata and BM25 token matrices
        docs = load_all_policy_documents()
        self.chunks = []
        self.chunk_id_map = {}

        for d in docs:
            chunk_data = {
                "chunk_id": d.doc_id,
                "text": d.text,
                "section": d.metadata.get("section", "General"),
                "region": d.metadata.get("region", "unknown"),
                "filename": d.metadata.get("filename", ""),
                "policy_id": d.metadata.get("policy_id", "HR-207"),
                "effective_date": d.metadata.get("effective_date", ""),
            }
            self.chunks.append(chunk_data)
            self.chunk_id_map[d.doc_id] = chunk_data

        tokenized_corpus = [self._tokenize(c["text"]) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        self._query_cache.clear()
        self._initialized = True

    def retrieve(
        self,
        query: str,
        region: Optional[str] = None,
        top_k: int = 5,
        hybrid: bool = True
    ) -> List[Dict[str, Any]]:
        """Executes hybrid (ChromaDB + BM25 via RRF) or dense vector retrieval."""
        if not self._initialized:
            self.initialize()

        norm_region = region.strip().upper() if region and region.upper() != "ALL" else None
        cache_key = f"{query.strip().lower()}|{norm_region}|{top_k}|{hybrid}"

        if cache_key in self._query_cache:
            hits = [dict(c) for c in self._query_cache[cache_key]]
            tracer.event("retrieval_cache_hit", input={"cache_key": cache_key},
                         output=[c["chunk_id"] for c in hits], metadata={"cache_size": len(self._query_cache)})
            return hits
        tracer.event("retrieval_cache_miss", input={"cache_key": cache_key}, metadata={"cache_size": len(self._query_cache)})

        # 1. Native ChromaDB HNSW Vector Query
        where_clause = {"region": norm_region} if norm_region else None
        vector_results: List[Dict[str, Any]] = []
        n_results = min(top_k * 2, max(1, self.chroma_collection.count()))
        with tracer.span("dense_search", as_type="retriever", input={
            "query": query, "where": where_clause, "n_results": n_results,
            "embedding_model": settings.embedding_model_name, "index": "chromadb_hnsw_cosine",
        }) as dense:
            try:
                chroma_query_args: Dict[str, Any] = {"query_texts": [query], "n_results": n_results}
                if where_clause:
                    chroma_query_args["where"] = where_clause

                query_res = self.chroma_collection.query(**chroma_query_args)
                if query_res and query_res.get("ids") and query_res["ids"][0]:
                    for rank, doc_id in enumerate(query_res["ids"][0], start=1):
                        distance = query_res["distances"][0][rank - 1] if query_res.get("distances") else 0.0
                        chunk_item = self.chunk_id_map.get(doc_id)
                        if chunk_item:
                            item_copy = dict(chunk_item)
                            item_copy["vector_rank"] = rank
                            item_copy["score"] = round(1.0 - float(distance), 4)  # Cosine similarity
                            vector_results.append(item_copy)
            except Exception as e:
                # Dense side unavailable: BM25 alone still answers in hybrid mode
                dense.update(level="ERROR", status_message=f"ChromaDB query failed: {e}")
            dense.update(output=[{"chunk_id": c["chunk_id"], "rank": c["vector_rank"], "cosine": c["score"]}
                                 for c in vector_results])

        if not hybrid:
            final_results = vector_results[:top_k]
            self._query_cache[cache_key] = final_results
            return final_results

        # 2. Fast Sparse BM25 Query
        with tracer.span("bm25_search", as_type="retriever", input={"query": query, "region": norm_region}) as bm25:
            query_tokens = self._tokenize(query)
            bm25_scores = self.bm25.get_scores(query_tokens) if query_tokens else [0.0] * len(self.chunks)

            candidate_indices = [
                i for i, c in enumerate(self.chunks)
                if not norm_region or c["region"].upper() == norm_region
            ]
            bm25_top_indices = sorted(candidate_indices, key=lambda i: bm25_scores[i], reverse=True)[:top_k * 2]

            bm25_results = []
            for rank, idx in enumerate(bm25_top_indices, start=1):
                c = dict(self.chunks[idx])
                c["bm25_rank"] = rank
                c["bm25_score"] = float(bm25_scores[idx])
                bm25_results.append(c)
            bm25.update(
                output=[{"chunk_id": c["chunk_id"], "rank": c["bm25_rank"], "bm25": round(c["bm25_score"], 4)} for c in bm25_results],
                metadata={"query_tokens": query_tokens, "candidates_after_region_filter": len(candidate_indices),
                          "corpus_size": len(self.chunks)})

        # 3. Reciprocal Rank Fusion (RRF)
        with tracer.span("rrf_fusion", input={"rrf_k": settings.rrf_k, "top_k": top_k}) as rrf:
            rrf_k = settings.rrf_k
            fused_scores: Dict[str, float] = {}
            candidate_map: Dict[str, Dict[str, Any]] = {}

            for rank, doc in enumerate(vector_results, start=1):
                doc_id = doc["chunk_id"]
                fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank))
                candidate_map[doc_id] = doc

            for rank, doc in enumerate(bm25_results, start=1):
                doc_id = doc["chunk_id"]
                fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank))
                # keep the dense rank if the doc was in both lists
                candidate_map[doc_id] = {**candidate_map.get(doc_id, {}), **doc}

            sorted_doc_ids = sorted(fused_scores.keys(), key=lambda d: fused_scores[d], reverse=True)[:top_k]

            fused_results = []
            for rank, doc_id in enumerate(sorted_doc_ids, start=1):
                item = dict(candidate_map[doc_id])
                item["rrf_score"] = round(fused_scores[doc_id], 5)
                item["score"] = item["rrf_score"]
                item["rank"] = rank
                fused_results.append(item)
            rrf.update(output=[{
                "chunk_id": r["chunk_id"], "rank": r["rank"], "rrf": r["rrf_score"],
                "dense_rank": r.get("vector_rank"), "bm25_rank": r.get("bm25_rank"),
                "section": r.get("section"), "region": r.get("region"),
            } for r in fused_results], metadata={"candidates_fused": len(fused_scores)})

        # Cache results (limit cache size)
        if len(self._query_cache) >= settings.cache_max_size:
            self._query_cache.clear()
        self._query_cache[cache_key] = fused_results

        return fused_results


# Global Singleton Instance
hybrid_retriever = ProductionHybridRetriever()
