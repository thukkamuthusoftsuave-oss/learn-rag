"""Tests for building the answer-quality report from traces.

The suite run itself needs an LLM, but everything after it - grouping, ranking
and writing the report - is pure data handling and is where a silent mistake
would be most costly: this is the artefact someone reads to decide what to fix.
"""

from policy_rag.evaluation import quality


def _trace(golden_id, label, query="a question", observation="something happened"):
    """Builds a labelled trace of the shape a suite run produces."""
    return {
        "trace_id": "t-" + golden_id,
        "golden_id": golden_id,
        "run_id": "eval-test",
        "label": label,
        "query": query,
        "observation": observation,
        "retrieval_ok": label != "RETRIEVAL_FAILURE",
    }


def test_report_ranks_problems_and_names_one_fix():
    """The report must end in a single actionable target, not a list of woes."""
    traces = [
        _trace("CORE-01", "CORRECT"),
        _trace("CORE-02", "CORRECT"),
        _trace("OOC-01", "CORRECT_REFUSAL"),
        _trace("EDGE-01", "GENERATION_FAILURE"),
        _trace("EDGE-02", "RETRIEVAL_FAILURE"),
        _trace("EDGE-03", "RETRIEVAL_FAILURE"),
    ]
    report = quality.build_report(traces, run_id="eval-test")

    assert report["summary"] == {"total": 6, "bugs": 3, "ok": 3}
    assert report["taxonomy"][0]["label"] == "RETRIEVAL_FAILURE"  # 2 x 5 = 10
    assert report["prediction"]["label"] == "RETRIEVAL_FAILURE"
    assert report["prediction"]["count"] == 2
    assert report["prediction"]["total"] == 6


def test_clean_run_produces_no_prediction():
    """Nothing failed means nothing to fix - the report must not invent a target."""
    report = quality.build_report([_trace("CORE-01", "CORRECT")], run_id="eval-test")
    assert report["summary"]["bugs"] == 0
    assert report["prediction"] is None


def test_empty_traces_do_not_crash_the_report():
    """Loading a report before anything has run is empty, not an error."""
    report = quality.build_report([], run_id=None)
    assert report["traces"] == []
    assert report["summary"]["total"] == 0
    assert report["prediction"] is None


def test_markdown_report_contains_the_three_sections(tmp_path):
    """Traces, taxonomy and prediction card - the report is useless missing any."""
    traces = [_trace("CORE-01", "CORRECT"), _trace("EDGE-01", "RETRIEVAL_FAILURE")]
    path = tmp_path / "answer-quality.md"
    quality.write_markdown_report(quality.build_report(traces, "eval-test"), path=path)

    text = path.read_text(encoding="utf-8")
    assert "## 1. Traces" in text
    assert "## 2. Error Taxonomy" in text
    assert "## 3. Prediction Card" in text
    assert "eval-test" in text
    assert "CORE-01" in text and "EDGE-01" in text
    assert "**Will not fix:**" in text  # the honest half of the card


def test_markdown_report_escapes_table_breaking_pipes(tmp_path):
    """A question containing a pipe must not shatter the Markdown table."""
    traces = [_trace("CORE-01", "CORRECT", query="cap for senior | probationary?")]
    path = tmp_path / "report.md"
    quality.write_markdown_report(quality.build_report(traces, "eval-test"), path=path)

    row = next(l for l in path.read_text(encoding="utf-8").splitlines() if "CORE-01" in l)
    assert row.count("|") == 6  # 5 columns => 6 delimiters, no extras leaked in


def test_report_written_to_a_missing_directory(tmp_path):
    """A fresh checkout has no reports/ directory yet."""
    path = tmp_path / "nested" / "reports" / "answer-quality.md"
    quality.write_markdown_report(quality.build_report([_trace("CORE-01", "CORRECT")]), path=path)
    assert path.exists()


def test_partial_run_is_labelled_as_partial(tmp_path):
    """A run cut short by quota must never read as a complete assessment."""
    traces = [_trace("CORE-01", "CORRECT"), _trace("CORE-02", "CORRECT")]
    report = quality.build_report(
        traces, run_id="eval-test",
        stopped_early="Daily API quota exhausted after 2 of 20 questions.",
    )
    assert report["coverage"] == {"asked": 2, "suite": 20}
    assert "quota" in report["stopped_early"]

    path = tmp_path / "report.md"
    quality.write_markdown_report(report, path=path)
    text = path.read_text(encoding="utf-8")
    assert "Partial run" in text
    assert "Questions asked: 2 of 20" in text


def test_complete_run_carries_no_partial_warning(tmp_path):
    """The warning must not appear when the whole suite was asked."""
    report = quality.build_report([_trace("CORE-01", "CORRECT")], run_id="eval-test")
    assert report["stopped_early"] is None

    path = tmp_path / "report.md"
    quality.write_markdown_report(report, path=path)
    assert "Partial run" not in path.read_text(encoding="utf-8")
