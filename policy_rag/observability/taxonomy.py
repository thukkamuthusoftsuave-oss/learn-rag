"""Error taxonomy: turning traces into a ranked list of what to fix next.

The method is deliberately the one a human analyst would follow, in this order:

1. **Observe.** Read the trace and write one honest sentence about what
   happened (``classify`` produces the observation before the label).
2. **Group.** Assign that observation to a named problem type.
3. **Rank.** Order the problem types by frequency x severity, not by how
   interesting they are.
4. **Predict.** State the single change to make next, what it should move and
   - just as importantly - what it will not fix (``prediction_card``).

Severity is calibrated for a policy assistant, where a confidently wrong
answer about someone's leave entitlement is worse than an awkward sentence.
"""

from collections import Counter

# Labels a trace can carry. Severity 0 means "not a bug".
LABEL_META = {
    "CORRECT": {
        "severity": 0,
        "display": "Correct answer",
    },
    "CORRECT_REFUSAL": {
        "severity": 0,
        "display": "Correct refusal (not a bug)",
    },
    "UNLABELED": {
        "severity": 0,
        "display": "Unlabeled (live traffic, no expected answer)",
    },
    "RETRIEVAL_FAILURE": {
        "severity": 5,
        "display": "Retrieval failure (wrong region / no doc)",
    },
    "GENERATION_FAILURE": {
        "severity": 4,
        "display": "Generation failure (right doc, wrong answer)",
    },
    "PIPELINE_ERROR": {
        "severity": 4,
        "display": "Pipeline error (request failed)",
    },
    "UNKNOWN": {
        "severity": 3,
        "display": "Unknown (needs manual inspection)",
    },
}

# The fix to reach for per problem type. Shared by the CLI report, the API and
# the web UI so the recommendation is written down in exactly one place.
REMEDIATION = {
    "RETRIEVAL_FAILURE": {
        "cause": (
            "Queries without a region filter let all six addenda compete in vector "
            "space. The highest cosine similarity wins regardless of which region "
            "the user is actually in."
        ),
        "change": (
            "Hybrid retrieval: fuse BM25 with the vector retriever using RRF. Region "
            "codes and section numbers in the query are exact-match targets for BM25, "
            "which lifts the correct addendum. Enabled by default (RAG_HYBRID)."
        ),
        "prediction": (
            "hit-rate@3 and MRR rise for region-explicit and exact-term queries. "
            "Correct refusals are unaffected."
        ),
        "will_not_fix": (
            "Fully ambiguous queries that name no region at all, and generation "
            "failures where the right document was already retrieved."
        ),
    },
    "GENERATION_FAILURE": {
        "cause": (
            "The correct document is retrieved but the model misreads it - typically "
            "a cap table whose row must be selected by employee type and service length."
        ),
        "change": (
            "Add a cross-encoder reranker (bge-reranker-base) so the decisive chunk "
            "lands first in the context window, or tighten the prompt to require "
            "reading the eligibility clause before the cap table."
        ),
        "prediction": (
            "Answer accuracy improves on table-reading questions. Retrieval metrics "
            "(hit-rate@k, MRR) stay flat, because retrieval was never the problem."
        ),
        "will_not_fix": "Retrieval failures, where the wrong document is delivered.",
    },
    "PIPELINE_ERROR": {
        "cause": "The request never completed - usually an API rate limit or a missing index.",
        "change": "Add backoff-and-retry around the LLM call and fail loudly when the index is missing.",
        "prediction": "Error traces drop to zero; answer quality metrics are unchanged.",
        "will_not_fix": "Anything about answer quality.",
    },
    "UNKNOWN": {
        "cause": "The trace does not match a known pattern.",
        "change": "Inspect the trace by hand and extend the taxonomy with what you find.",
        "prediction": "-",
        "will_not_fix": "-",
    },
}


def classify(trace: dict, expectation: dict = None) -> dict:
    """Labels one trace and writes the observation that justifies the label.

    Retrieval and generation are separated first, because they need different
    fixes: if the expected source is not in the top 3 chunks the fault is
    retrieval, and no prompt change will help.

    Args:
        trace: Trace fields - at minimum ``is_refusal`` and ``retrieved_chunks``.
        expectation: Optional gold data with ``expected_type`` (``"answer"`` or
            ``"refusal"``) and ``expected_source``. Live chat traffic has none,
            and is labelled ``UNLABELED``.

    Returns:
        Dict with ``label``, ``observation``, ``retrieval_ok`` and ``top_sources``.
    """
    chunks = trace.get("retrieved_chunks") or []
    sources = [c.get("source_file", "unknown") for c in chunks]
    top_sources = sources[:3]

    if trace.get("error"):
        return {
            "label": "PIPELINE_ERROR",
            "observation": f"Request failed before an answer was produced: {trace['error']}",
            "retrieval_ok": False,
            "top_sources": top_sources,
        }

    expectation = expectation or {}
    expected_type = expectation.get("expected_type") or trace.get("expected_type")
    expected_source = expectation.get("expected_source") or trace.get("expected_source")
    is_refusal = bool(trace.get("is_refusal"))
    retrieval_ok = expected_source is None or expected_source in top_sources

    if not expected_type:
        verdict = "refused" if is_refusal else "answered"
        return {
            "label": "UNLABELED",
            "observation": (
                f"Live question, no expected answer recorded. The assistant {verdict} "
                f"from {top_sources or 'no chunks'}; a reviewer must judge it."
            ),
            "retrieval_ok": retrieval_ok,
            "top_sources": top_sources,
        }

    if expected_type == "refusal":
        if is_refusal:
            label = "CORRECT_REFUSAL"
            observation = (
                "Correctly refused - the topic does not appear in any of the six "
                "regional addenda, and the assistant said so instead of inventing one."
            )
        else:
            label = "GENERATION_FAILURE"
            observation = (
                "Answered a question the corpus cannot support. The topic is out of "
                "corpus, so this is a hallucination, not a retrieval problem."
            )
    elif is_refusal:
        if retrieval_ok:
            label = "GENERATION_FAILURE"
            observation = (
                f"Retrieval was fine ({expected_source} was in the top 3) but the "
                "assistant refused anyway - the refusal instruction is firing too eagerly."
            )
        else:
            label = "RETRIEVAL_FAILURE"
            observation = (
                f"{expected_source} never reached the top 3 chunks, so there was "
                "nothing to answer from. The root cause is retrieval, not the prompt."
            )
    elif retrieval_ok:
        label = "CORRECT"
        observation = (
            f"{expected_source} was in the top 3 and the assistant answered from it. "
            "Wording still needs a human read to confirm the numbers."
        )
    else:
        label = "RETRIEVAL_FAILURE"
        observation = (
            f"{expected_source} missing from the top 3 (rank 1 was "
            f"{top_sources[0] if top_sources else 'nothing'}), so the answer was "
            "delivered confidently from the wrong region's policy."
        )

    return {
        "label": label,
        "observation": observation,
        "retrieval_ok": retrieval_ok,
        "top_sources": top_sources,
    }


def build_taxonomy(traces: list) -> list:
    """Groups traces by label and ranks the groups by frequency x severity.

    Args:
        traces: Labelled traces.

    Returns:
        Rows with ``label``, ``display``, ``count``, ``severity``, ``score``
        and ``trace_ids``, ordered worst-first.
    """
    counts = Counter(t.get("label", "UNKNOWN") for t in traces)
    rows = []
    for label, count in counts.items():
        meta = LABEL_META.get(label, {"severity": 2, "display": label})
        rows.append({
            "label": label,
            "display": meta["display"],
            "count": count,
            "severity": meta["severity"],
            "score": count * meta["severity"],
            "trace_ids": [t["trace_id"] for t in traces if t.get("label") == label],
        })
    rows.sort(key=lambda r: (-r["score"], -r["count"], r["label"]))
    return rows


def summarise(traces: list) -> dict:
    """Counts traces by outcome.

    Args:
        traces: Labelled traces.

    Returns:
        Dict with ``total``, ``bugs`` (severity > 0) and ``ok``.
    """
    total = len(traces)
    bugs = sum(1 for t in traces if severity_of(t.get("label")) > 0)
    return {"total": total, "bugs": bugs, "ok": total - bugs}


def severity_of(label: str) -> int:
    """Returns the severity (0-5) of a label, defaulting to 2 for unknown ones."""
    return LABEL_META.get(label, {"severity": 2})["severity"]


def prediction_card(taxonomy: list, total_traces: int) -> dict:
    """Picks the single highest-scoring problem and states the fix for it.

    Args:
        taxonomy: Ranked rows from ``build_taxonomy``.
        total_traces: Traces the ranking was computed over, for the frequency line.

    Returns:
        Dict describing the chosen problem and its remediation, or None when no
        problem with severity above zero was found.
    """
    top = next((row for row in taxonomy if row["severity"] > 0), None)
    if top is None:
        return None
    remedy = REMEDIATION.get(top["label"], REMEDIATION["UNKNOWN"])
    return {
        "label": top["label"],
        "display": top["display"],
        "count": top["count"],
        "total": total_traces,
        "severity": top["severity"],
        "score": top["score"],
        **remedy,
    }
