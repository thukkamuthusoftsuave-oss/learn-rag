"""Permanent regression tests built from Week 5 failures.

"Turning last week's real failures into permanent tests,
so they can't come back unnoticed."

Covers:
- EDGE-01: Part-time employee exclusion (0 days) despite 3 years tenure
- EDGE-02: Resignation without notice 50% payout penalty in NA
- EDGE-07: Sabbatical dual-fact completeness (4 weeks duration AND 5 years service)
- OOC-01/02/03/04: Forced refusal safety on out-of-corpus topics
- Rule assertion checks (exact refusal sentinel, citation syntax, source retrieval)
- Judge scoring and validation reliability
"""

import pytest

from policy_rag import config
from policy_rag.evaluation import datasets
from policy_rag.evaluation.judge import (
    check_citation_assertion,
    check_refusal_assertion,
    check_source_assertion,
    judge_answer,
    run_rule_assertions,
)
from policy_rag.evaluation.judge_validation import compute_agreement_metrics, validate_judge
from policy_rag.evaluation.test_suite import compute_delta, evaluate_queries


def test_regression_edge01_part_time_disqualification():
    """EDGE-01 failure: model previously awarded 20 days based on 3 yrs service,
    ignoring Section 4.7 part-time exclusion.
    """
    golden = datasets.by_id("EDGE-01")

    # Buggy answer (pre-fix baseline): awards 20 days
    buggy_trace = {
        "trace_id": "t-edge01-bug",
        "golden_id": "EDGE-01",
        "answer": (
            "You have worked for 3 years, so you are eligible for 20 carry-over days. "
            "[[HR-207 Section 4.2]](chunk_1:addendum_US.txt)"
        ),
        "is_refusal": False,
        "retrieved_chunks": [
            {"rank": 1, "source_file": "addendum_US.txt", "text_preview": "Senior > 2 yrs: 20 days"},
            {"rank": 2, "source_file": "addendum_US.txt", "text_preview": "Part-time employees are not eligible"},
        ],
    }
    buggy_result = judge_answer(buggy_trace, golden)
    assert buggy_result["verdict"] == "FAIL", "Buggy trace awarding 20 days must fail"

    # Fixed answer: correctly identifies 0 days / part-time exclusion
    fixed_trace = {
        "trace_id": "t-edge01-fixed",
        "golden_id": "EDGE-01",
        "answer": (
            "Part-time employees working fewer than 40 hours per week do not meet the continuous-service "
            "definition and are not eligible for carry-over (0 days), regardless of your 3 years of tenure. "
            "[[HR-207 Section 4.7]](chunk_2:addendum_US.txt)"
        ),
        "is_refusal": False,
        "retrieved_chunks": [
            {"rank": 1, "source_file": "addendum_US.txt", "text_preview": "Part-time employees are not eligible"},
            {"rank": 2, "source_file": "addendum_US.txt", "text_preview": "Senior > 2 yrs: 20 days"},
        ],
    }
    fixed_result = judge_answer(fixed_trace, golden)
    assert fixed_result["verdict"] == "PASS", "Fixed trace stating 0 days must pass"
    assert fixed_result["score"] >= 4


def test_regression_edge02_resignation_without_notice():
    """EDGE-02 failure: model previously missed the 50% payout reduction penalty."""
    golden = datasets.by_id("EDGE-02")

    # Buggy answer: cites 100% voluntary termination without notice penalty
    buggy_trace = {
        "trace_id": "t-edge02-bug",
        "golden_id": "EDGE-02",
        "answer": (
            "On voluntary termination, your unused days are paid at 100% of the base daily rate. "
            "[[HR-207 Section 4.5]](c1:addendum_NA.txt)"
        ),
        "is_refusal": False,
        "retrieved_chunks": [{"rank": 1, "source_file": "addendum_NA.txt", "text_preview": "paid at 100%"}],
    }
    assert judge_answer(buggy_trace, golden)["verdict"] == "FAIL"

    # Fixed answer: includes the 50% reduction penalty
    fixed_trace = {
        "trace_id": "t-edge02-fixed",
        "golden_id": "EDGE-02",
        "answer": (
            "Resignation without the contractual notice period reduces payout to 50% for all employee types. "
            "[[HR-207 Section 4.5]](c1:addendum_NA.txt)"
        ),
        "is_refusal": False,
        "retrieved_chunks": [{"rank": 1, "source_file": "addendum_NA.txt", "text_preview": "reduces payout to 50%"}],
    }
    assert judge_answer(fixed_trace, golden)["verdict"] == "PASS"


def test_regression_edge07_sabbatical_completeness():
    """EDGE-07 failure: model previously answered 4 weeks but omitted 5-year tenure condition."""
    golden = datasets.by_id("EDGE-07")

    # Incomplete answer: duration only
    incomplete_trace = {
        "trace_id": "t-edge07-incomplete",
        "golden_id": "EDGE-07",
        "answer": (
            "In EMEA, employees receive a 4-week sabbatical fully paid at base salary. "
            "[[HR-207 Section 4.3]](c1:addendum_EMEA.txt)"
        ),
        "is_refusal": False,
        "retrieved_chunks": [{"rank": 1, "source_file": "addendum_EMEA.txt", "text_preview": "4-week sabbatical after 5 years"}],
    }
    assert judge_answer(incomplete_trace, golden)["verdict"] == "FAIL"

    # Complete answer: both 4 weeks and 5 years
    complete_trace = {
        "trace_id": "t-edge07-complete",
        "golden_id": "EDGE-07",
        "answer": (
            "In EMEA, after 5 years of continuous service, employees are eligible for a 4-week sabbatical. "
            "[[HR-207 Section 4.3]](c1:addendum_EMEA.txt)"
        ),
        "is_refusal": False,
        "retrieved_chunks": [{"rank": 1, "source_file": "addendum_EMEA.txt", "text_preview": "4-week sabbatical after 5 years"}],
    }
    assert judge_answer(complete_trace, golden)["verdict"] == "PASS"


def test_regression_forced_refusal_rules():
    """OOC questions must strictly return the exact refusal sentinel."""
    for q_id in ("OOC-01", "OOC-02", "OOC-03", "OOC-04"):
        golden = datasets.by_id(q_id)

        # Proper refusal passes
        safe_trace = {
            "trace_id": f"t-{q_id}-safe",
            "golden_id": q_id,
            "answer": config.REFUSAL_SENTINEL,
            "is_refusal": True,
            "retrieved_chunks": [],
        }
        res = judge_answer(safe_trace, golden)
        assert res["verdict"] == "PASS"
        assert res["score"] == 5

        # Hallucinated response fails
        hallucinated_trace = {
            "trace_id": f"t-{q_id}-hallucinated",
            "golden_id": q_id,
            "answer": "Maternity leave in EMEA provides 16 weeks of paid leave. [[Policy]](c1:doc.txt)",
            "is_refusal": False,
            "retrieved_chunks": [],
        }
        res_bad = judge_answer(hallucinated_trace, golden)
        assert res_bad["verdict"] == "FAIL"


def test_rule_assertions_refusal_assertion():
    """Rule assertion: refusal detection."""
    # Answer expected, but got refusal -> assertion must fail
    res = check_refusal_assertion(config.REFUSAL_SENTINEL, is_refusal=True, expected_type="answer")
    assert not res["passed"]

    # Refusal expected, and got refusal -> assertion must pass
    res_ok = check_refusal_assertion(config.REFUSAL_SENTINEL, is_refusal=True, expected_type="refusal")
    assert res_ok["passed"]


def test_rule_assertions_citation_syntax():
    """Rule assertion: citation presence."""
    # Valid citations
    assert check_citation_assertion("Cap is 10 days. [[Section 4.2]](c1:addendum_US.txt)", "answer")["passed"]
    assert check_citation_assertion("Cap is 10 days. [[addendum_NA.txt]]", "answer")["passed"]

    # Missing citation
    assert not check_citation_assertion("Cap is 10 days with no source.", "answer")["passed"]


def test_rule_assertions_source_retrieval():
    """Rule assertion: expected source must be in top 3 retrieved chunks."""
    chunks = [
        {"rank": 1, "source_file": "addendum_US.txt"},
        {"rank": 2, "source_file": "addendum_NA.txt"},
        {"rank": 3, "source_file": "addendum_UK.txt"},
    ]
    assert check_source_assertion(chunks, "addendum_US.txt")["passed"]
    assert not check_source_assertion(chunks, "addendum_APAC.txt")["passed"]


def test_judge_validation_metrics():
    """Validates statistical agreement metrics calculation."""
    human = [1, 1, 1, 0, 0]
    judge = [1, 1, 1, 0, 1]  # 1 false positive

    metrics = compute_agreement_metrics(human, judge)
    assert metrics["total"] == 5
    assert metrics["tp"] == 3
    assert metrics["tn"] == 1
    assert metrics["fp"] == 1
    assert metrics["fn"] == 0
    assert metrics["agreement_rate"] == 80.0
    assert 0.0 < metrics["cohens_kappa"] <= 1.0


def test_test_suite_evaluation_and_delta():
    """Evaluates the test suite scoring and before/after delta calculation."""
    before = evaluate_queries(mode="baseline")  # Baseline: 85%
    assert before["overall_score_pct"] == 85.0
    assert before["scores_by_type"]["core_entitlement"]["pass_rate_pct"] == 100.0
    assert before["scores_by_type"]["edge_qualification"]["pass_rate_pct"] == 62.5

    # Simulated improved traces with EDGE-01 and EDGE-07 resolved
    improved_traces = [
        {
            "golden_id": "EDGE-01",
            "answer": (
                "Part-time employees working fewer than 40 hours per week are not eligible "
                "for carry-over (0 days) under Section 4.7. [[HR-207 Section 4.7]](c2:addendum_US.txt)"
            ),
            "is_refusal": False,
            "retrieved_chunks": [{"rank": 1, "source_file": "addendum_US.txt", "text_preview": "Section 4.7: 0 days"}],
        },
        {
            "golden_id": "EDGE-07",
            "answer": (
                "After 5 years of continuous service, EMEA employees receive a 4-week sabbatical. "
                "[[HR-207 Section 4.3]](c1:addendum_EMEA.txt)"
            ),
            "is_refusal": False,
            "retrieved_chunks": [{"rank": 1, "source_file": "addendum_EMEA.txt", "text_preview": "4-week after 5 years"}],
        },
    ]

    after = evaluate_queries(improved_traces)
    assert after["overall_score_pct"] > before["overall_score_pct"]

    delta = compute_delta(before, after)
    assert delta["overall_delta_pct"] > 0
    assert len(delta["fixed_items"]) == 3  # EDGE-01, EDGE-02, EDGE-07 resolved
    assert len(delta["regressed_items"]) == 0
