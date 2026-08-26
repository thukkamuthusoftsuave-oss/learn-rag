"""Tests for the trace log."""

import json

from policy_rag.observability.traces import TraceStore, normalise


def _store(tmp_path):
    """Returns a TraceStore backed by a temporary file."""
    return TraceStore(path=tmp_path / "traces.jsonl")


def test_append_and_read_round_trip(tmp_path):
    """A written trace comes back with its fields intact."""
    store = _store(tmp_path)
    store.append({"query": "cap in US?", "region": "US", "label": "CORRECT"})
    traces = store.read()
    assert len(traces) == 1
    assert traces[0]["query"] == "cap in US?"
    assert traces[0]["region"] == "US"


def test_reading_an_absent_log_is_not_an_error(tmp_path):
    """A fresh install has no log yet; that is empty, not broken."""
    assert _store(tmp_path).read() == []


def test_missing_fields_are_defaulted(tmp_path):
    """Partial records must not break readers downstream."""
    store = _store(tmp_path)
    written = store.append({"query": "anything"})
    assert written["trace_id"] and written["timestamp"]
    assert written["label"] == "UNLABELED"


def test_legacy_field_names_are_migrated():
    """Traces written before the rename still load."""
    migrated = normalise({"query": "q", "correct_source": "addendum_US.txt"})
    assert migrated["expected_source"] == "addendum_US.txt"


def test_top_sources_are_derived_from_retrieved_chunks():
    """The summary field is filled in when a caller omits it."""
    migrated = normalise({
        "retrieved_chunks": [
            {"source_file": "a.txt"}, {"source_file": "b.txt"},
            {"source_file": "c.txt"}, {"source_file": "d.txt"},
        ]
    })
    assert migrated["top_sources"] == ["a.txt", "b.txt", "c.txt"]


def test_a_corrupt_line_does_not_break_reading(tmp_path):
    """A half-written final line must not take the whole log down."""
    store = _store(tmp_path)
    store.append({"query": "first"})
    with open(store.path, "a", encoding="utf-8") as handle:
        handle.write('{"query": "truncated"')
    assert [t["query"] for t in store.read()] == ["first"]


def test_filters_and_limit(tmp_path):
    """Reads can be narrowed to one run, one source, or the most recent few."""
    store = _store(tmp_path)
    store.append({"query": "a", "run_id": "run-1", "source": "evaluation"})
    store.append({"query": "b", "run_id": "run-2", "source": "chat"})
    store.append({"query": "c", "run_id": "run-2", "source": "chat"})

    assert [t["query"] for t in store.read(run_id="run-2")] == ["b", "c"]
    assert [t["query"] for t in store.read(source="chat")] == ["b", "c"]
    assert [t["query"] for t in store.read(limit=1)] == ["c"]


def test_latest_run_returns_only_that_run(tmp_path):
    """Loading the last evaluation must not mix in an older one."""
    store = _store(tmp_path)
    store.append({"query": "old", "run_id": "run-1", "source": "evaluation"})
    store.append({"query": "new", "run_id": "run-2", "source": "evaluation"})
    store.append({"query": "chatter", "run_id": "live", "source": "chat"})

    assert store.latest_run_id(source="evaluation") == "run-2"
    assert [t["query"] for t in store.latest_run(source="evaluation")] == ["new"]


def test_prune_keeps_the_most_recent_and_stays_valid_json(tmp_path):
    """Trimming the log must leave a readable file behind."""
    store = _store(tmp_path)
    for i in range(5):
        store.append({"query": f"q{i}"})
    assert store.prune(keep=2) == 3
    lines = store.path.read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(line)["query"] for line in lines] == ["q3", "q4"]


def test_clear_removes_everything(tmp_path):
    """Clearing reports how much it removed and leaves an empty log."""
    store = _store(tmp_path)
    store.append({"query": "a"})
    store.append({"query": "b"})
    assert store.clear() == 2
    assert store.read() == []
