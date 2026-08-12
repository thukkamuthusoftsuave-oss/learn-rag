"""End-to-end smoke checks against the live RAG query engine.

Covers the three behaviors the assignment cares about: forced refusal on
out-of-corpus questions, region metadata filtering, and the bonus
precision/completeness scenario (US part-time employee who does not meet the
continuous-service definition). Requires a built index (see ``ingest.py``)
and a ``GEMINI_API_KEY`` for real answers.
"""

from retriever import query_rag

# (name, query, region) triples; region None means no metadata filter.
SCENARIOS = [
    {
        "name": "Out-of-domain refusal",
        "query": "What is the maternity leave policy in EMEA?",
        "region": None,
    },
    {
        "name": "Region filtering (US)",
        "query": "What is the carry-over cap for a probationary employee?",
        "region": "US",
    },
    {
        "name": "Bonus challenge scenario",
        # Part-time US employee: does not meet the continuous-service
        # definition in Section 4.1, so the 4.2 cap should not apply.
        "query": "I am a part-time employee (20 hours/week) in the US and I have worked here for 3 years. How many carry-over days do I get?",
        "region": "US",
    },
]


def run_verification(verbose: bool = True) -> list:
    """Runs every scenario through ``query_rag`` with the detailed envelope.

    Args:
        verbose: When True, prints each scenario name and answer.

    Returns:
        List of dicts with ``name``, ``query``, ``region``, ``answer`` and
        ``is_refusal`` for each scenario.
    """
    results = []
    for scenario in SCENARIOS:
        if verbose:
            print(f"Testing {scenario['name']}...")
        envelope = query_rag(scenario["query"], region=scenario["region"], detailed=True)
        results.append({
            "name": scenario["name"],
            "query": scenario["query"],
            "region": scenario["region"],
            "answer": envelope["answer"],
            "is_refusal": envelope["is_refusal"],
        })
        if verbose:
            print(f"Answer: {envelope['answer']}\n")
    return results


def main() -> None:
    """Runs all verification scenarios with console output."""
    run_verification(verbose=True)


if __name__ == "__main__":
    main()
