"""Integrity checks on the golden question sets.

These questions are the project's evidence base. A duplicated id, a question
that silently loses its expected source, or a refusal case that quietly gains
one would corrupt every report built on them without failing anything else.
"""

import pytest

from policy_rag.evaluation import datasets


def test_ids_are_unique():
    """Ids are used as report keys and trace labels, so collisions matter."""
    ids = [q.id for q in datasets.ALL_QUERIES]
    assert len(ids) == len(set(ids))


def test_answerable_queries_name_an_expected_source():
    """Every scorable question must say which document should be retrieved."""
    for query in datasets.CORE_QUERIES + datasets.EDGE_QUERIES:
        assert query.expected_type == "answer"
        assert query.expected_source, f"{query.id} has no expected source"
        assert query.expected_section, f"{query.id} has no expected section"


def test_refusal_queries_have_no_expected_source():
    """An out-of-corpus question cannot have a correct document, by definition."""
    for query in datasets.REFUSAL_QUERIES:
        assert query.expected_type == "refusal"
        assert query.expected_source is None


def test_ambiguous_queries_are_flagged_and_unscored():
    """Ambiguity must be declared, not inferred from a missing field."""
    for query in datasets.HARD_QUERIES:
        if query.expected_source is None:
            assert query.ambiguous, f"{query.id} has no expected source but is not flagged ambiguous"


def test_expected_sources_exist_in_the_corpus():
    """Expected sources must be real files, or the metrics measure nothing."""
    if not datasets.CORE_QUERIES:
        pytest.skip("no golden queries")
    from policy_rag import config

    if not config.DATA_DIR.exists():
        pytest.skip("corpus not generated yet - run `policy-rag corpus`")
    available = {p.name for p in config.DATA_DIR.glob("*.txt")}
    for query in datasets.ALL_QUERIES:
        if query.expected_source:
            assert query.expected_source in available, f"{query.id} points at a missing file"


def test_suites_are_composed_as_documented():
    """The suites the CLI exposes must contain what their docstrings claim."""
    assert len(datasets.RETRIEVAL_SUITE) == len(datasets.CORE_QUERIES) + len(datasets.HARD_QUERIES)
    assert len(datasets.ANSWER_QUALITY_SUITE) == (
        len(datasets.CORE_QUERIES) + len(datasets.REFUSAL_QUERIES) + len(datasets.EDGE_QUERIES)
    )
    assert len(datasets.SMOKE_SUITE) == 3


def test_expectation_carries_the_fields_the_taxonomy_needs():
    """The labeller reads these keys; a rename here would silently unlabel runs."""
    expectation = datasets.CORE_QUERIES[0].expectation()
    assert set(expectation) == {"golden_id", "expected_type", "expected_source", "expected_section"}
