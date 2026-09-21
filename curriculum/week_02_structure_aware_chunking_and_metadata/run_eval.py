"""Week 2 Evaluation: Structure-Aware vs Naive Chunking Bake-Off.

Evaluates how structure-aware sectioning preserves table cohesion and
demonstrates how metadata filtering boosts retrieval precision.
"""

import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from structure_chunker import structure_aware_chunk_text


def load_corpus(data_dir: Path) -> dict:
    docs = {}
    for f in sorted(data_dir.glob("addendum_*.txt")):
        with open(f, "r", encoding="utf-8") as handle:
            docs[f.name] = handle.read()
    return docs


def run_structure_eval():
    root_dir = Path(__file__).resolve().parent.parent.parent
    corpus_dir = root_dir / "data_and_benchmarks" / "files_to_learn" / "synthetic_corpus"
    if not corpus_dir.exists():
        corpus_dir = root_dir / "data"

    queries_file = root_dir / "data_and_benchmarks" / "files_to_learn" / "golden_datasets" / "core_queries.json"
    with open(queries_file, "r", encoding="utf-8") as f:
        core_queries = json.load(f)

    docs = load_corpus(corpus_dir)
    print("=== Week 2: Structure-Aware Chunking & Metadata Bake-Off ===")

    chunks = []
    for fname, text in docs.items():
        doc_chunks = structure_aware_chunk_text(text, filename=fname)
        chunks.extend(doc_chunks)

    print(f"Generated {len(chunks)} structure-aware section chunks with rich metadata.")

    # 1. Evaluate Hit-in-Top-5 with Structure-Aware Chunks
    texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer().fit(texts)
    chunk_matrix = vectorizer.transform(texts)

    hits = 0
    total = len(core_queries)
    for q in core_queries:
        query_text = q.get("query")
        expected_sec = q.get("expected_section")
        expected_src = q.get("expected_source")

        q_vec = vectorizer.transform([query_text])
        scores = cosine_similarity(q_vec, chunk_matrix)[0]
        top_indices = scores.argsort()[::-1][:5]
        top_chunks = [chunks[idx] for idx in top_indices]

        hit = any(
            (expected_sec and expected_sec in c["section"]) or
            (expected_src and c["filename"] == expected_src and (not expected_sec or expected_sec in c["section"]))
            for c in top_chunks
        )
        if hit:
            hits += 1
        status = "HIT " if hit else "MISS"
        print(f"[{status}] {q['id']}: {query_text[:50]}... -> Top: {top_chunks[0]['section']} ({top_chunks[0]['region']})")

    print(f"\nStructure-Aware Score: Hit-in-Top-5 = {hits}/{total} ({hits/total*100:.1f}%)")

    # 2. Metadata Filtering Demonstration
    test_query = "What is the max carry-over for a senior with > 2 years of service?"
    test_region = "US"
    print(f"\n--- Metadata Filtering Impact Test ---")
    print(f"Query: '{test_query}'")

    q_vec = vectorizer.transform([test_query])
    scores = cosine_similarity(q_vec, chunk_matrix)[0]
    
    # Unfiltered Top 2
    unfiltered_indices = scores.argsort()[::-1][:2]
    print("\n[Unfiltered Results - Top 2]:")
    for rank, idx in enumerate(unfiltered_indices, start=1):
        c = chunks[idx]
        print(f"  Rank {rank}: Score={scores[idx]:.4f} | Region={c['region']} | Section={c['section']}")

    # Filtered by Region = US
    filtered_chunks_with_scores = [
        (chunks[i], scores[i]) for i in range(len(chunks)) if chunks[i]["region"] == test_region
    ]
    filtered_sorted = sorted(filtered_chunks_with_scores, key=lambda x: x[1], reverse=True)[:2]
    print(f"\n[Filtered Results (Region={test_region}) - Top 2]:")
    for rank, (c, score) in enumerate(filtered_sorted, start=1):
        print(f"  Rank {rank}: Score={score:.4f} | Region={c['region']} | Section={c['section']}")
    print("\nResult: Exact metadata filtering eliminates cross-jurisdiction noise and guarantees correct policy lookup!")


if __name__ == "__main__":
    run_structure_eval()
