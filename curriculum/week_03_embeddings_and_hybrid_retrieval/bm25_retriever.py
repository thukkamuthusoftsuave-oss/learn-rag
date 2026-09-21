"""Week 3: BM25 Sparse Keyword Retriever.

Implements tokenization and BM25 scoring using the rank-bm25 package.
"""

from typing import List, Dict, Any
from rank_bm25 import BM25Okapi


class BM25Retriever:
    """Fast lexical BM25 retriever for exact keyword matching."""

    def __init__(self, corpus_chunks: List[Dict[str, Any]]):
        self.chunks = corpus_chunks
        self.corpus_tokenized = [
            self._tokenize(c["text"]) for c in corpus_chunks
        ]
        self.bm25 = BM25Okapi(self.corpus_tokenized)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # Simple whitespace/alphanumeric lower-cased tokenization
        import re
        return re.findall(r"\w+", text.lower())

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        scores = self.bm25.get_scores(query_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for rank, idx in enumerate(top_indices, start=1):
            chunk = dict(self.chunks[idx])
            chunk["bm25_score"] = float(scores[idx])
            chunk["bm25_rank"] = rank
            results.append(chunk)
        return results
