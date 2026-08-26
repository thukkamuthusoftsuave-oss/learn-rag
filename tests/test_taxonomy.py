"""Tests for the error taxonomy.

The labeller is the part of the system that decides what gets fixed next, so
the separation it draws - retrieval failure versus generation failure - has to
hold exactly.
"""

from policy_rag.observability import taxonomy


def _trace(is_refusal=False, sources=(), error=None):
    """Builds a minimal trace with the given retrieved sources."""
    return {
        "is_refusal": is_refusal,
        "retrieved_chunks": [{"source_file": s} for s in sources],
        "error": error,
    }


ANSWER_EXPECTED = {"expected_type": "answer", "expected_source": "addendum_US.txt"}
REFUSAL_EXPECTED = {"expected_type": "refusal", "expected_source": None}


def test_wrong_document_is_a_retrieval_failure():
    """Answering from another region's policy is a retrieval fault, not a prompt one."""
    verdict = taxonomy.classify(_trace(sources=["addendum_UK.txt"]), ANSWER_EXPECTED)
    assert verdict["label"] == "RETRIEVAL_FAILURE"
    assert verdict["retrieval_ok"] is False


def test_right_document_but_refused_is_a_generation_failure():
    """When retrieval delivered the document, refusing is the model's fault."""
    verdict = taxonomy.classify(_trace(is_refusal=True, sources=["addendum_US.txt"]), ANSWER_EXPECTED)
    assert verdict["label"] == "GENERATION_FAILURE"
    assert verdict["retrieval_ok"] is True


def test_answering_an_out_of_corpus_question_is_a_hallucination():
    """Out-of-corpus questions must be refused; answering one is a generation failure."""
    verdict = taxonomy.classify(_trace(sources=["addendum_US.txt"]), REFUSAL_EXPECTED)
    assert verdict["label"] == "GENERATION_FAILURE"


def test_correct_refusal_is_not_a_bug():
    """The refusal path working is a pass, and must not inflate the failure count."""
    verdict = taxonomy.classify(_trace(is_refusal=True), REFUSAL_EXPECTED)
    assert verdict["label"] == "CORRECT_REFUSAL"
    assert taxonomy.severity_of(verdict["label"]) == 0


def test_live_traffic_is_unlabeled_not_guessed():
    """Without gold data the labeller must abstain rather than invent a verdict."""
    verdict = taxonomy.classify(_trace(sources=["addendum_US.txt"]))
    assert verdict["label"] == "UNLABELED"
    assert taxonomy.severity_of(verdict["label"]) == 0


def test_errors_are_labelled_before_anything_else():
    """A failed request must never be scored as an answer-quality result."""
    verdict = taxonomy.classify(_trace(error="RateLimit: 429"), ANSWER_EXPECTED)
    assert verdict["label"] == "PIPELINE_ERROR"


def test_expected_source_below_rank_three_counts_as_missed():
    """Only the top three chunks reach the model, so rank four is a miss."""
    sources = ["a.txt", "b.txt", "c.txt", "addendum_US.txt"]
    verdict = taxonomy.classify(_trace(sources=sources), ANSWER_EXPECTED)
    assert verdict["label"] == "RETRIEVAL_FAILURE"


def test_taxonomy_ranks_by_frequency_times_severity():
    """A rarer but more severe problem must outrank a common trivial one."""
    traces = (
        [{"trace_id": f"g{i}", "label": "GENERATION_FAILURE"} for i in range(2)]
        + [{"trace_id": f"r{i}", "label": "RETRIEVAL_FAILURE"} for i in range(2)]
        + [{"trace_id": f"c{i}", "label": "CORRECT"} for i in range(10)]
    )
    ranked = taxonomy.build_taxonomy(traces)
    assert ranked[0]["label"] == "RETRIEVAL_FAILURE"  # 2 x 5 beats 2 x 4
    assert ranked[0]["score"] == 10
    assert taxonomy.summarise(traces) == {"total": 14, "bugs": 4, "ok": 10}


def test_prediction_card_names_the_top_problem_and_its_limits():
    """The card must state a fix and what that fix will not solve."""
    ranked = taxonomy.build_taxonomy([{"trace_id": "r1", "label": "RETRIEVAL_FAILURE"}])
    card = taxonomy.prediction_card(ranked, total_traces=1)
    assert card["label"] == "RETRIEVAL_FAILURE"
    assert card["change"] and card["will_not_fix"]


def test_no_prediction_card_when_nothing_failed():
    """A clean run must not manufacture something to fix."""
    ranked = taxonomy.build_taxonomy([{"trace_id": "c1", "label": "CORRECT"}])
    assert taxonomy.prediction_card(ranked, total_traces=1) is None
