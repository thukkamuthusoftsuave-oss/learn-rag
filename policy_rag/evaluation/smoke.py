"""End-to-end smoke checks - the fastest useful confidence signal.

Three questions, each covering one behaviour the assistant must never lose:

1. **Forced refusal.** An out-of-corpus topic must produce the exact refusal
   sentence, not a plausible invention.
2. **Region filtering.** A question that names no region must still be answered
   from the region the metadata filter selects.
3. **Reading the prerequisite clause.** A part-time employee does not meet the
   continuous-service definition, so the obvious cap-table row does not apply.

Requires a built index and an ``OPENROUTER_API_KEY``. For the full picture use
``policy-rag eval quality``; this is the check to run before a demo.
"""

from policy_rag.evaluation.datasets import SMOKE_SUITE
from policy_rag.observability.traces import new_run_id


def run_smoke_checks(verbose: bool = True) -> list:
    """Runs every smoke scenario through the assistant.

    Args:
        verbose: Print each scenario and its answer as it completes.

    Returns:
        List of dicts with ``id``, ``query``, ``region``, ``answer``,
        ``is_refusal``, ``label`` and ``passed`` for each scenario.
    """
    from policy_rag.chat.service import answer

    run_id = new_run_id("smoke")
    results = []
    for golden in SMOKE_SUITE:
        if verbose:
            print(f"Checking {golden.id}: {golden.note}")
        trace = answer(
            golden.query,
            region=golden.region,
            run_id=run_id,
            source="evaluation",
            expectation=golden.expectation(),
        )
        # A check passes when the taxonomy did not classify it as a failure.
        passed = trace["label"] in ("CORRECT", "CORRECT_REFUSAL")
        results.append({
            "id": golden.id,
            "query": golden.query,
            "region": golden.region,
            "answer": trace["answer"],
            "is_refusal": trace["is_refusal"],
            "label": trace["label"],
            "passed": passed,
        })
        if verbose:
            print(f"  {'PASS' if passed else 'FAIL'} [{trace['label']}]")
            print(f"  {trace['answer']}\n")

    if verbose:
        passed_count = sum(1 for r in results if r["passed"])
        print(f"Smoke checks: {passed_count}/{len(results)} passed")
    return results


def main() -> None:
    """Runs the smoke checks from the command line."""
    results = run_smoke_checks(verbose=True)
    raise SystemExit(0 if all(r["passed"] for r in results) else 1)


if __name__ == "__main__":
    main()
