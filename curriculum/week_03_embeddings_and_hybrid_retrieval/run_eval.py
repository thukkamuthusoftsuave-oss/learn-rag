"""Week 3 Evaluation: Dense vs BM25 vs Hybrid (RRF) Retrieval.

Computes Hit-Rate@1, Hit-Rate@3, and Mean Reciprocal Rank (MRR)
demonstrating how RRF recovers exact section and numeric queries.
"""

import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from bm25_retriever import BM25Retriever
from hybrid_fusion import reciprocal_rank_fusion


def load_corpus(data_dir: Path) -> list:
    import re
    chunks = []
    for f in sorted(data_dir.glob("addendum_*.txt")):
        with open(f, "r", encoding="utf-8") as handle:
            text = handle.read()
        region_match = re.search(r"Region:\s*([A-Za-z]+)", text)
        region = region_match.group(1).strip() if region_match else "unknown"
        
        parts = re.split(r"(HR-207\s+Section\s+\d+\.\d+[^\n]*)", text, flags=re.IGNORECASE)
        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            body = parts[i + 1].strip() if (i + 1) < len(parts) else ""
            sec_num = re.search(r"Section\s+(\d+\.\d+)", header)
            s_tag = f"HR-207 Section {sec_num.group(1)}" if sec_num else header
            chunks.append({
                "chunk_id": f"{region}_{s_tag.replace(' ', '_')}",
                "text": f"{header}\n{body}",
                "section": s_tag,
                "region": region,
                "filename": f.name
            })
    return chunks


def evaluate_retrieval(chunks: list, queries: list, top_k: int = 5):
    # Setup Vector-like (TF-IDF/Cosine) and BM25
    texts = [c["text"] for c in chunks]
    tfidf = TfidfVectorizer().fit(texts)
    doc_matrix = tfidf.transform(texts)
    bm25 = BM25Retriever(chunks)

    vector_hits_1, vector_hits_3, vector_rr = 0, 0, 0.0
    hybrid_hits_1, hybrid_hits_3, hybrid_rr = 0, 0, 0.0
    total = len(queries)

    print("=== Week 3: Dense vs Hybrid Retrieval Benchmark ===")
    print(f"Corpus chunks: {len(chunks)} | Benchmark queries: {total}\n")

    for q in queries:
        query_text = q.get("query")
        expected_sec = q.get("expected_section")
        expected_src = q.get("expected_source")

        # 1. Vector retrieval
        q_vec = tfidf.transform([query_text])
        scores = cosine_similarity(q_vec, doc_matrix)[0]
        top_vec_indices = scores.argsort()[::-1][:top_k]
        vector_results = []
        for rank, idx in enumerate(top_vec_indices, start=1):
            c = dict(chunks[idx])
            c["vector_rank"] = rank
            vector_results.append(c)

        # 2. BM25 retrieval
        bm25_results = bm25.retrieve(query_text, top_k=top_k)

        # 3. Hybrid fusion
        fused_results = reciprocal_rank_fusion(vector_results, bm25_results, rrf_k=60, top_k=top_k)

        # Helper to find rank of expected document
        def get_rank(results):
            for r, c in enumerate(results, start=1):
                if expected_sec and expected_sec in c["section"]:
                    return r
                if expected_src and c["filename"] == expected_src and (not expected_sec or expected_sec in c["section"]):
                    return r
            return None

        v_rank = get_rank(vector_results)
        h_rank = get_rank(fused_results)

        if v_rank == 1: vector_hits_1 += 1
        if v_rank and v_rank <= 3: vector_hits_3 += 1
        if v_rank: vector_rr += (1.0 / v_rank)

        if h_rank == 1: hybrid_hits_1 += 1
        if h_rank and h_rank <= 3: hybrid_hits_3 += 1
        if h_rank: hybrid_rr += (1.0 / h_rank)

        print(f"Query {q.get('id')}: Vector Rank = {v_rank or 'Miss'}, Hybrid Rank = {h_rank or 'Miss'} | {query_text[:45]}...")

    print("\n--- Summary Metrics ---")
    print(f"Vector-Only: Hit@1 = {vector_hits_1}/{total} ({vector_hits_1/total*100:.1f}%), Hit@3 = {vector_hits_3}/{total} ({vector_hits_3/total*100:.1f}%), MRR = {vector_rr/total:.3f}")
    print(f"Hybrid(RRF): Hit@1 = {hybrid_hits_1}/{total} ({hybrid_hits_1/total*100:.1f}%), Hit@3 = {hybrid_hits_3}/{total} ({hybrid_hits_3/total*100:.1f}%), MRR = {hybrid_rr/total:.3f}")


def run_benchmark():
    root_dir = Path(__file__).resolve().parent.parent.parent
    corpus_dir = root_dir / "data_and_benchmarks" / "files_to_learn" / "synthetic_corpus"
    if not corpus_dir.exists(): corpus_dir = root_dir / "data"

    queries_file = root_dir / "data_and_benchmarks" / "files_to_learn" / "golden_datasets" / "hard_queries.json"
    if not queries_file.exists():
        queries_file = root_dir / "data_and_benchmarks" / "files_to_learn" / "golden_datasets" / "core_queries.json"

    with open(queries_file, "r", encoding="utf-8") as f:
        queries = json.load(f)

    chunks = load_corpus(corpus_dir)
    evaluate_retrieval(chunks, queries)


if __name__ == "__main__":
    run_benchmark()
