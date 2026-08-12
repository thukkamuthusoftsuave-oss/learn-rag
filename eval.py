"""Offline retrieval evaluation: naive vs structure-aware chunking.

Measures hit-in-top-5 with TF-IDF + cosine similarity, comparing the naive
4-line chunker against the structure-aware section chunker over the 8
pre-written known-answer questions. The corpus is read from ``data/`` at
runtime so the evaluation always reflects the shipped addenda (the previous
inline copy of the documents could silently drift from ``setup_data.py``).
"""

import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from chunker import naive_chunker, structure_aware_chunker

DATA_DIR = "data"

# The 8 known-answer questions were written before any retrieval ran and must
# never be tailored to observed results (recorded project convention).
QUESTIONS = [
    {"q": "What is the carry-over cap for a probationary employee in NA?", "ans_section": "HR-207 Section 4.2", "region": "NA"},
    {"q": "What is the carry-over cap for a regular employee with 1 year of service in EMEA?", "ans_section": "HR-207 Section 4.2", "region": "EMEA"},
    {"q": "What is the carry-over cap for a senior employee in APAC?", "ans_section": "HR-207 Section 4.2", "region": "APAC"},
    {"q": "When does the HR-207 policy become effective in LATAM?", "ans_section": "Header", "region": "LATAM"},
    {"q": "What defines continuous service in US for the carry-over policy?", "ans_section": "HR-207 Section 4.1", "region": "US"},
    {"q": "Who is eligible for the sabbatical in UK?", "ans_section": "HR-207 Section 4.3", "region": "UK"},
    {"q": "What is the max carry-over for a senior with > 2 years of service in US?", "ans_section": "HR-207 Section 4.2", "region": "US"},
    {"q": "Does a regular employee in NA get 15 days carry-over cap?", "ans_section": "HR-207 Section 4.2", "region": "NA"},
]

# Query used to demonstrate the impact of metadata filtering on ranking.
FILTER_DEMO_QUERY = "What is the max carry-over for a senior with > 2 years of service?"
FILTER_DEMO_REGION = "US"


def load_corpus(data_dir: str = DATA_DIR) -> dict:
    """Reads every addendum file into a ``{filename: text}`` dict.

    Args:
        data_dir: Directory containing the ``addendum_*.txt`` files.

    Returns:
        Mapping of file name to full file text.
    """
    docs = {}
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".txt"):
            with open(os.path.join(data_dir, fname), "r", encoding="utf-8") as f:
                docs[fname] = f.read()
    return docs


def run_retrieval(chunks: list, query: str, region_filter: str = None) -> list:
    """Ranks chunks against a query with TF-IDF + cosine similarity.

    Args:
        chunks: Chunk dicts as produced by the chunkers in ``chunker.py``.
        query: The query string.
        region_filter: Optional region code; when set, only chunks from that
            region (or with unknown region) participate in ranking.

    Returns:
        Up to 5 results, each a dict with ``chunk`` and ``score``.
    """
    if region_filter:
        filtered_chunks = [c for c in chunks if c['region'] == region_filter or c['region'] == 'unknown']
    else:
        filtered_chunks = chunks

    texts = [c['text'] for c in filtered_chunks]
    vectorizer = TfidfVectorizer()
    if not texts:
        return []

    try:
        tfidf_matrix = vectorizer.fit_transform(texts + [query])
    except ValueError:
        return []  # empty vocabulary

    cosine_sim = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
    top_indices = cosine_sim.argsort()[::-1]

    results = []
    for i in top_indices[:5]:
        results.append({
            'chunk': filtered_chunks[i],
            'score': cosine_sim[i]
        })
    return results


def run_evaluation(verbose: bool = True) -> dict:
    """Runs the chunker bake-off and the metadata-filtering demonstration.

    Args:
        verbose: When True, prints per-question hits and the filtering demo
            in the same format used to document ``results.md``.

    Returns:
        Dict with ``naive_hits``, ``smart_hits``, ``per_question`` details and
        the ``filter_demo`` unfiltered/filtered result lists.
    """
    docs = load_corpus()

    naive_chunks = []
    smart_chunks = []
    for fname, text in docs.items():
        naive_chunks.extend(naive_chunker(text, fname))
        smart_chunks.extend(structure_aware_chunker(text, fname))

    naive_hits = 0
    smart_hits = 0
    per_question = []

    if verbose:
        print("=== Evaluation ===")
    for q_idx, q in enumerate(QUESTIONS):
        if verbose:
            print(f"Q{q_idx + 1}: {q['q']}")

        # Naive: hit means the expected section header text appears in a chunk.
        n_res = run_retrieval(naive_chunks, q['q'])
        n_hit = any(q['ans_section'] in c['chunk']['text'] for c in n_res)
        if n_hit:
            naive_hits += 1

        # Smart: hit means a chunk's section metadata matches exactly.
        s_res = run_retrieval(smart_chunks, q['q'])
        s_hit = any(q['ans_section'] == c['chunk']['section'] for c in s_res)
        if s_hit:
            smart_hits += 1

        per_question.append({
            "q": q['q'], "ans_section": q['ans_section'],
            "naive_hit": n_hit, "smart_hit": s_hit,
        })
        if verbose:
            print(f"  Naive Hit: {n_hit}")
            print(f"  Smart Hit: {s_hit}")

    if verbose:
        print(f"\nNaive Score: {naive_hits}/8")
        print(f"Smart Score: {smart_hits}/8")

    # Metadata filter demonstration.
    res_unfiltered = run_retrieval(smart_chunks, FILTER_DEMO_QUERY)
    res_filtered = run_retrieval(smart_chunks, FILTER_DEMO_QUERY, region_filter=FILTER_DEMO_REGION)

    if verbose:
        print("\n--- Unfiltered ---")
        for r in res_unfiltered[:2]:
            print(f"Score: {r['score']:.4f} | Region: {r['chunk']['region']} | Chunk: {r['chunk']['chunk_id']}")
        print(f"--- Filtered (Region={FILTER_DEMO_REGION}) ---")
        for r in res_filtered[:2]:
            print(f"Score: {r['score']:.4f} | Region: {r['chunk']['region']} | Chunk: {r['chunk']['chunk_id']}")

    return {
        "naive_hits": naive_hits,
        "smart_hits": smart_hits,
        "per_question": per_question,
        "filter_demo": {
            "query": FILTER_DEMO_QUERY,
            "region": FILTER_DEMO_REGION,
            "unfiltered": res_unfiltered,
            "filtered": res_filtered,
        },
    }


def main() -> None:
    """Runs the evaluation with full console output."""
    run_evaluation(verbose=True)


if __name__ == "__main__":
    main()
