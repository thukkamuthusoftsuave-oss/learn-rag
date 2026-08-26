"""Chunking bake-off: naive line splitting vs structure-aware sectioning.

The measurement that justifies the indexing strategy. Both chunkers run over
the same corpus, both are ranked with the same TF-IDF + cosine retriever, and
both are scored on the same eight known-answer questions - so the only variable
is where the documents were cut.

A second demonstration shows what metadata buys once it exists: the same query
run with and without a region filter, where filtering moves the correct
region's section to rank 1.

This suite is deliberately independent of the vector index. It reads the corpus
straight from ``config.DATA_DIR``, so it can be run before anything is ingested
and cannot be confounded by embedding-model behaviour.
"""

import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from policy_rag import config
from policy_rag.corpus.chunking import naive_chunker, structure_aware_chunker
from policy_rag.evaluation.datasets import CORE_QUERIES

TOP_K = 5

# Same question with and without a region filter, to show the ranking shift.
FILTER_DEMO_QUERY = "What is the max carry-over for a senior with > 2 years of service?"
FILTER_DEMO_REGION = "US"


def load_corpus(data_dir=None) -> dict:
    """Reads every addendum file into a ``{filename: text}`` dict.

    Args:
        data_dir: Directory containing the ``addendum_*.txt`` files. Defaults
            to ``config.DATA_DIR``.

    Returns:
        Mapping of file name to full file text.
    """
    data_dir = str(data_dir or config.DATA_DIR)
    docs = {}
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".txt"):
            with open(os.path.join(data_dir, fname), "r", encoding="utf-8") as handle:
                docs[fname] = handle.read()
    return docs


def rank_chunks(chunks: list, query: str, region_filter: str = None) -> list:
    """Ranks chunks against a query with TF-IDF + cosine similarity.

    Args:
        chunks: Chunk dicts from either chunker.
        query: The query string.
        region_filter: Optional region code; when set, only chunks from that
            region (or with unknown region) participate in ranking.

    Returns:
        Up to ``TOP_K`` results, each a dict with ``chunk`` and ``score``.
    """
    candidates = chunks
    if region_filter:
        candidates = [c for c in chunks if c["region"] in (region_filter, "unknown")]
    texts = [c["text"] for c in candidates]
    if not texts:
        return []

    try:
        matrix = TfidfVectorizer().fit_transform(texts + [query])
    except ValueError:
        return []  # Empty vocabulary - nothing rankable.

    similarities = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    ranked = similarities.argsort()[::-1]
    return [{"chunk": candidates[i], "score": float(similarities[i])} for i in ranked[:TOP_K]]


def evaluate_chunking() -> dict:
    """Scores both chunkers on hit-in-top-5 and runs the filtering demo.

    A hit means the chunk that would answer the question is in the top five.
    The naive chunker has no section metadata, so it is credited whenever the
    expected section header text appears inside a retrieved chunk - the most
    generous reading available to it.

    Returns:
        Dict with ``naive_hits``, ``structure_hits``, ``total``,
        ``per_question`` rows and the ``filter_demo`` result lists.
    """
    docs = load_corpus()

    naive_chunks = []
    structure_chunks = []
    for fname, text in docs.items():
        naive_chunks.extend(naive_chunker(text, fname))
        structure_chunks.extend(structure_aware_chunker(text, fname))

    per_question = []
    naive_hits = 0
    structure_hits = 0
    for golden in CORE_QUERIES:
        naive_results = rank_chunks(naive_chunks, golden.query)
        naive_hit = any(golden.expected_section in r["chunk"]["text"] for r in naive_results)

        structure_results = rank_chunks(structure_chunks, golden.query)
        structure_hit = any(golden.expected_section == r["chunk"]["section"] for r in structure_results)

        naive_hits += int(naive_hit)
        structure_hits += int(structure_hit)
        per_question.append({
            "id": golden.id,
            "query": golden.query,
            "expected_section": golden.expected_section,
            "naive_hit": naive_hit,
            "structure_hit": structure_hit,
        })

    return {
        "naive_hits": naive_hits,
        "structure_hits": structure_hits,
        "total": len(CORE_QUERIES),
        "per_question": per_question,
        "filter_demo": {
            "query": FILTER_DEMO_QUERY,
            "region": FILTER_DEMO_REGION,
            "unfiltered": rank_chunks(structure_chunks, FILTER_DEMO_QUERY),
            "filtered": rank_chunks(structure_chunks, FILTER_DEMO_QUERY, region_filter=FILTER_DEMO_REGION),
        },
    }


def print_report(result: dict) -> None:
    """Prints the bake-off as a console report.

    Args:
        result: Output of ``evaluate_chunking``.
    """
    rule = "=" * 74
    print()
    print(rule)
    print("  CHUNKING BAKE-OFF - hit-in-top-5, TF-IDF + cosine")
    print(rule)
    for row in result["per_question"]:
        print(f"\n  {row['id']}: {row['query'][:66]}")
        print(f"    expected section : {row['expected_section']}")
        print(f"    naive            : {'HIT' if row['naive_hit'] else 'MISS'}")
        print(f"    structure-aware  : {'HIT' if row['structure_hit'] else 'MISS'}")

    total = result["total"]
    print(f"\n  Naive           : {result['naive_hits']}/{total}")
    print(f"  Structure-aware : {result['structure_hits']}/{total}")

    demo = result["filter_demo"]
    print(f"\n{rule}")
    print("  METADATA FILTERING - same query, with and without a region filter")
    print(rule)
    print(f"  Query: {demo['query']}")
    print("\n  Unfiltered:")
    for entry in demo["unfiltered"][:2]:
        chunk = entry["chunk"]
        print(f"    score={entry['score']:.4f}  region={chunk['region']:<6} chunk={chunk['chunk_id']}")
    print(f"\n  Filtered (region={demo['region']}):")
    for entry in demo["filtered"][:2]:
        chunk = entry["chunk"]
        print(f"    score={entry['score']:.4f}  region={chunk['region']:<6} chunk={chunk['chunk_id']}")
    print()


def main() -> None:
    """Runs the bake-off from the command line."""
    print_report(evaluate_chunking())


if __name__ == "__main__":
    main()
