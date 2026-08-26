"""Retrieval benchmark: does the assistant fetch the right document?

Retrieval failures and generation failures need opposite fixes, so they are
measured separately. This suite measures retrieval alone - it never calls the
LLM - by running each golden question through both retrieval modes and
comparing where the expected document lands:

- **hit-rate@1** - was it the very first chunk? (What the model reads first.)
- **hit-rate@3** - was it in the top three? (What the model reads at all.)
- **MRR** - mean reciprocal rank, which keeps improving as the right document
  climbs even when hit-rate@3 is already saturated.

Two sets are reported separately because a single average would hide the
result: on region-explicit questions the biencoder is already at ceiling for
hit-rate@3, and hybrid retrieval shows up as a ranking gain; on the exact-term
set it recovers hits outright.
"""

from policy_rag import config
from policy_rag.evaluation.datasets import CORE_QUERIES, HARD_QUERIES

K1, K3 = 1, 3
NOT_FOUND = 999


def retrieve(retriever, query: str, top_k: int) -> list:
    """Runs one query through a retriever without generating an answer.

    Args:
        retriever: A retriever from ``policy_rag.retrieval``.
        query: The question text.
        top_k: Maximum chunks to keep.

    Returns:
        Ranked list of dicts with ``rank``, ``source_file``, ``score``,
        ``region`` and a short text preview.
    """
    from llama_index.core import QueryBundle

    nodes = retriever.retrieve(QueryBundle(query_str=query))
    results = []
    for index, scored_node in enumerate(nodes[:top_k]):
        node = scored_node.node
        metadata = node.metadata or {}
        results.append({
            "rank": index + 1,
            "source_file": metadata.get("source_file", "unknown"),
            "score": round(scored_node.score, 4) if scored_node.score is not None else None,
            "region": metadata.get("region", "unknown"),
            "text_preview": (node.text or "")[:100].replace("\n", " "),
        })
    return results


def first_correct_rank(retrieved: list, expected_source: str) -> int:
    """Returns the 1-based rank of the expected source, or ``NOT_FOUND``."""
    for chunk in retrieved:
        if chunk["source_file"] == expected_source:
            return chunk["rank"]
    return NOT_FOUND


def label_outcome(rank: int, expected_source: str) -> str:
    """Labels one retrieval result as OK, a failure, or unscorable."""
    if expected_source is None:
        return "AMBIGUOUS"
    return "RETRIEVAL_OK" if rank <= K3 else "RETRIEVAL_FAILURE"


def _score_rows(rows: list) -> dict:
    """Computes hit-rate@1, hit-rate@3 and MRR over scorable rows.

    Args:
        rows: Per-query result rows.

    Returns:
        Dict with ``hit1``, ``hit3``, ``mrr`` and ``n`` (rows actually scored).
        Ambiguous questions are excluded - scoring them would invent a number.
    """
    scorable = [r for r in rows if r["expected_source"] and not r["ambiguous"]]
    n = len(scorable)
    if n == 0:
        return {"hit1": 0.0, "hit3": 0.0, "mrr": 0.0, "n": 0}
    return {
        "hit1": round(sum(1 for r in scorable if r["hit1"]) / n, 4),
        "hit3": round(sum(1 for r in scorable if r["hit3"]) / n, 4),
        "mrr": round(sum(r["rr"] for r in scorable) / n, 4),
        "n": n,
    }


def _run_set(retriever, queries: list, top_k: int) -> list:
    """Runs one question set through one retriever and scores every question."""
    rows = []
    for golden in queries:
        retrieved = retrieve(retriever, golden.query, top_k)
        rank = first_correct_rank(retrieved, golden.expected_source) if golden.expected_source else NOT_FOUND
        rows.append({
            "id": golden.id,
            "query": golden.query,
            "expected_source": golden.expected_source,
            "note": golden.note,
            "ambiguous": golden.ambiguous,
            "rank": None if rank == NOT_FOUND else rank,
            "label": label_outcome(rank, golden.expected_source),
            "hit1": rank <= K1,
            "hit3": rank <= K3,
            "rr": round(1 / rank, 4) if rank < NOT_FOUND else 0.0,
            "retrieved": retrieved[:K3],
        })
    return rows


def evaluate_retrieval(top_k: int = None) -> dict:
    """Compares vector-only against hybrid retrieval across both question sets.

    Args:
        top_k: Chunks each retriever fetches. Defaults to ``config.DEFAULT_TOP_K``.

    Returns:
        Dict with ``top_k``, ``metrics`` (per set and overall, before and
        after), ``comparison`` (one row per question) and ``unfixed`` (the
        questions hybrid retrieval does not rescue).
    """
    from policy_rag.retrieval import build_retriever

    top_k = config.DEFAULT_TOP_K if top_k is None else top_k
    baseline = build_retriever(region=None, top_k=top_k, hybrid=False)
    hybrid = build_retriever(region=None, top_k=top_k, hybrid=True)

    before_core = _run_set(baseline, CORE_QUERIES, top_k)
    after_core = _run_set(hybrid, CORE_QUERIES, top_k)
    before_hard = _run_set(baseline, HARD_QUERIES, top_k)
    after_hard = _run_set(hybrid, HARD_QUERIES, top_k)

    before_all = before_core + before_hard
    after_all = after_core + after_hard

    comparison = []
    for before, after in zip(before_all, after_all):
        comparison.append({
            "id": before["id"],
            "query": before["query"],
            "expected_source": before["expected_source"],
            "note": before["note"],
            "ambiguous": before["ambiguous"],
            "before": {k: before[k] for k in ("rank", "label", "hit1", "hit3", "rr", "retrieved")},
            "after": {k: after[k] for k in ("rank", "label", "hit1", "hit3", "rr", "retrieved")},
            "rank_improved": bool(before["expected_source"]) and after["rr"] > before["rr"],
            "rank_regressed": bool(before["expected_source"]) and after["rr"] < before["rr"],
            "newly_fixed": bool(before["expected_source"]) and not before["hit3"] and after["hit3"],
            "still_failing": bool(before["expected_source"]) and not after["hit3"],
        })

    return {
        "top_k": top_k,
        "metrics": {
            "core": {"before": _score_rows(before_core), "after": _score_rows(after_core)},
            "hard": {"before": _score_rows(before_hard), "after": _score_rows(after_hard)},
            "all": {"before": _score_rows(before_all), "after": _score_rows(after_all)},
        },
        "comparison": comparison,
        "unfixed": [row for row in comparison if row["still_failing"] or row["ambiguous"]],
    }


def print_report(result: dict, verbose: bool = False) -> None:
    """Prints the benchmark as a console report.

    Args:
        result: Output of ``evaluate_retrieval``.
        verbose: Also print a text preview of each retrieved chunk.
    """
    rule = "=" * 74
    print()
    print(rule)
    print("  RETRIEVAL BENCHMARK - vector-only vs hybrid (BM25 + vector, RRF)")
    print(f"  top_k={result['top_k']}, no region filter (worst case for retrieval)")
    print(rule)

    for set_key, title in (
        ("core", "Region named in the query (8 known-answer questions)"),
        ("hard", "Exact-term / no region named (ambiguous case excluded)"),
        ("all", "All scorable questions"),
    ):
        before = result["metrics"][set_key]["before"]
        after = result["metrics"][set_key]["after"]
        print(f"\n  {title}  [n={after['n']}]")
        for metric, label in (("hit1", "hit-rate@1"), ("hit3", "hit-rate@3"), ("mrr", "MRR       ")):
            delta = after[metric] - before[metric]
            sign = "+" if delta >= 0 else ""
            print(f"    {label}  {before[metric]:.3f} -> {after[metric]:.3f}   ({sign}{delta:.4f})")

    print(f"\n{rule}")
    print("  PER-QUESTION COMPARISON")
    print(rule)
    for row in result["comparison"]:
        if row["ambiguous"]:
            status = "AMBIGUOUS (excluded from metrics)"
        elif row["newly_fixed"]:
            status = "FIXED by hybrid"
        elif row["still_failing"]:
            status = "STILL FAILING"
        elif row["rank_improved"]:
            status = "rank improved"
        elif row["rank_regressed"]:
            status = "rank regressed"
        else:
            status = "unchanged"
        before_rank = row["before"]["rank"] or "not found"
        after_rank = row["after"]["rank"] or "not found"
        print(f"\n  {row['id']}: {row['query'][:66]}")
        print(f"    expected : {row['expected_source'] or '(none - ' + row['note'] + ')'}")
        print(f"    rank     : {before_rank} -> {after_rank}   [{status}]")
        if verbose:
            for chunk in row["after"]["retrieved"]:
                print(f"      [{chunk['rank']}] {chunk['source_file']} score={chunk['score']}")
                print(f"           {chunk['text_preview']}")

    print(f"\n{rule}")
    print("  WHAT HYBRID RETRIEVAL DOES NOT FIX")
    print(rule)
    for row in result["unfixed"]:
        reason = "no single correct source" if row["ambiguous"] else "expected document still outside the top 3"
        print(f"  {row['id']}: {reason}.")
    print("  * Generation failures: right document retrieved, wrong answer written.")
    print("    Measure those with `policy-rag eval quality`, not here.")
    print("  * Questions naming no region: BM25 has nothing to match on either.")
    print("    The fix is a region filter, not a better retriever.")
    print()


def main() -> None:
    """Runs the benchmark from the command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Retrieval benchmark: vector-only vs hybrid")
    parser.add_argument("--verbose", "-v", action="store_true", help="print retrieved chunk previews")
    parser.add_argument("--top-k", type=int, default=None, dest="top_k", help="chunks per retriever")
    args = parser.parse_args()
    print_report(evaluate_retrieval(top_k=args.top_k), verbose=args.verbose)


if __name__ == "__main__":
    main()
