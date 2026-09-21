"""Week 1 Evaluation: Naive Chunking Baseline.

Demonstrates the baseline hit-in-top-5 score of naive line-splitting
over the HR-207 policy corpus using TF-IDF + Cosine Similarity.
"""

import os
import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from naive_chunker import naive_chunk_text


def load_corpus(data_dir: Path) -> dict:
    docs = {}
    for f in sorted(data_dir.glob("addendum_*.txt")):
        with open(f, "r", encoding="utf-8") as handle:
            docs[f.name] = handle.read()
    return docs


def run_naive_benchmark():
    # Locate corpus and queries
    root_dir = Path(__file__).resolve().parent.parent.parent
    corpus_dir = root_dir / "data_and_benchmarks" / "files_to_learn" / "synthetic_corpus"
    if not corpus_dir.exists():
        corpus_dir = root_dir / "data"

    queries_file = root_dir / "data_and_benchmarks" / "files_to_learn" / "golden_datasets" / "core_queries.json"
    if queries_file.exists():
        with open(queries_file, "r", encoding="utf-8") as f:
            core_queries = json.load(f)
    else:
        from policy_rag.evaluation.datasets import CORE_QUERIES
        from dataclasses import asdict
        core_queries = [asdict(q) for q in CORE_QUERIES]

    docs = load_corpus(corpus_dir)
    print(f"=== Week 1: Naive Chunking Benchmark ===")
    print(f"Loaded {len(docs)} corpus documents from {corpus_dir}")

    # Chunk corpus with naive chunker
    all_chunks = []
    for fname, text in docs.items():
        doc_chunks = naive_chunk_text(text, lines_per_chunk=4)
        for c in doc_chunks:
            c["filename"] = fname
            all_chunks.append(c)

    print(f"Generated {len(all_chunks)} naive chunks (4 lines each).")

    # Evaluate Hit-in-Top-5
    hits = 0
    total = len(core_queries)
    results = []

    texts = [c["text"] for c in all_chunks]
    vectorizer = TfidfVectorizer().fit(texts)
    chunk_matrix = vectorizer.transform(texts)

    for q in core_queries:
        qid = q.get("id")
        query_text = q.get("query")
        expected_sec = q.get("expected_section")
        expected_src = q.get("expected_source")

        q_vec = vectorizer.transform([query_text])
        scores = cosine_similarity(q_vec, chunk_matrix)[0]
        top_indices = scores.argsort()[::-1][:5]
        top_chunks = [all_chunks[idx] for idx in top_indices]

        # Check if the expected section appears in top 5
        hit = any(
            (expected_sec and expected_sec in c["text"]) or 
            (expected_src and c["filename"] == expected_src and (not expected_sec or expected_sec in c["text"]))
            for c in top_chunks
        )
        if hit:
            hits += 1

        results.append({
            "id": qid,
            "query": query_text,
            "hit": hit,
            "top_match_preview": top_chunks[0]["text"][:60].replace("\n", " ") if top_chunks else "None"
        })

    print(f"\nBenchmark Results:")
    for r in results:
        status = "HIT " if r["hit"] else "MISS"
        print(f"[{status}] {r['id']}: {r['query'][:55]}...")

    hit_rate = (hits / total) * 100
    print(f"\nFinal Score: Hit-in-Top-5 = {hits}/{total} ({hit_rate:.1f}%)")
    print(f"Notice: Naive chunking fragments tables across line cuts, causing a low hit rate on expanded corpuses.")


if __name__ == "__main__":
    run_naive_benchmark()
